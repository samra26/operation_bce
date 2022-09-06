import torch
from torch.nn import functional as F
from conformer import build_model
import numpy as np
import os
import cv2
import time
from torch.utils.tensorboard import SummaryWriter
from torchvision.utils import make_grid
writer = SummaryWriter('log/run' + time.strftime("%d-%m"))
import torch.nn as nn
import argparse
import os.path as osp
import os
size_coarse = (10, 10)



class Solver(object):
    def __init__(self, train_loader, test_loader, config):
        self.train_loader = train_loader
        self.test_loader = test_loader
        self.config = config
        self.iter_size = config.iter_size
        self.show_every = config.show_every
        #self.build_model()
        self.net = build_model(self.config.network, self.config.arch)
        #self.net.eval()
        if config.mode == 'test':
            print('Loading pre-trained model for testing from %s...' % self.config.model)
            self.net.load_state_dict(torch.load(self.config.model, map_location=torch.device('cpu')))
        if config.mode == 'train':
            if self.config.load == '':
                print("Loading pre-trained imagenet weights for fine tuning")
                self.net.JLModule.load_pretrained_model(self.config.pretrained_model
                                                        if isinstance(self.config.pretrained_model, str)
                                                        else self.config.pretrained_model[self.config.network])
                # load pretrained backbone
            else:
                print('Loading pretrained model to resume training')
                self.net.load_state_dict(torch.load(self.config.load))  # load pretrained model
        
        if self.config.cuda:
            self.net = self.net.cuda()

        self.lr = self.config.lr
        self.wd = self.config.wd

        self.optimizer = torch.optim.Adam(self.net.parameters(), lr=self.lr, weight_decay=self.wd)

        #self.print_network(self.net, 'Conformer based SOD Structure')

    # print the network information and parameter numbers
    def print_network(self, model, name):
        num_params_t = 0
        num_params=0
        for p in model.parameters():
            if p.requires_grad:
                num_params_t += p.numel()
            else:
                num_params += p.numel()
        print(name)
        print(model)
        print("The number of trainable parameters: {}".format(num_params_t))
        print("The number of parameters: {}".format(num_params))

    # build the network
    '''def build_model(self):
        self.net = build_model(self.config.network, self.config.arch)

        if self.config.cuda:
            self.net = self.net.cuda()

        self.lr = self.config.lr
        self.wd = self.config.wd

        self.optimizer = torch.optim.Adam(self.net.parameters(), lr=self.lr, weight_decay=self.wd)

        self.print_network(self.net, 'JL-DCF Structure')'''

    def test(self):
        print('Testing...')
        time_s = time.time()
        img_num = len(self.test_loader)
        for i, data_batch in enumerate(self.test_loader):
            images, name, im_size, depth = data_batch['image'], data_batch['name'][0], np.asarray(data_batch['size']), \
                                           data_batch['depth']
            with torch.no_grad():
                if self.config.cuda:
                    device = torch.device(self.config.device_id)
                    images = images.to(device)
                    depth = depth.to(device)

                #input = torch.cat((images, depth), dim=0)
                preds,e_rgbd0,e_rgbd1= self.net(images,depth)
                #print(e_rgbd01.shape)
                preds = F.interpolate(preds, tuple(im_size), mode='bilinear', align_corners=True)
                pred = np.squeeze(torch.sigmoid(preds)).cpu().data.numpy()
                #print(pred.shape)
                pred = (pred - pred.min()) / (pred.max() - pred.min() + 1e-8)
                multi_fuse = 255 * pred
                filename = os.path.join(self.config.test_folder, name[:-4] + '_convtran.png')
                cv2.imwrite(filename, multi_fuse)
   
                '''#e_rgbd01 = F.interpolate(e_rgbd01, tuple(im_size), mode='bilinear', align_corners=True)
                e_rgbd01 = np.squeeze(torch.sigmoid(Att[10])).cpu().data.numpy()
                print(e_rgbd01.shape)
                #e_rgbd01 = (e_rgbd01-e_rgbd01.min()) / (e_rgbd01.max() - e_rgbd01.min() + 1e-8)
                #e_rgbd01 = 255 * e_rgbd01
                filename = os.path.join(self.config.test_folder, name[:-4] + '_edge.png')
                a=cv2.imwrite(filename, e_rgbd01)
                print(a)
                #e_rgbd11 = F.interpolate(e_rgbd11, tuple(im_size), mode='bilinear', align_corners=True)
                e_rgbd11 = np.squeeze(torch.sigmoid(Att[11])).cpu().data.numpy()
                print(e_rgbd11.shape)
                e_rgbd11 = (e_rgbd11-e_rgbd11.min()) / (e_rgbd11.max() - e_rgbd11.min() + 1e-8)
                e_rgbd11 = 255 * e_rgbd11
                filename = os.path.join(self.config.test_folder, name[:-5] + '_edge.png')
                cv2.imwrite(filename, e_rgbd11)

                #e_rgbd21 = F.interpolate(e_rgbd21, tuple(im_size), mode='bilinear', align_corners=True)
                e_rgbd21 = np.squeeze(torch.sigmoid(Att[9])).cpu().data.numpy()

                e_rgbd21 = (e_rgbd21-e_rgbd21.min()) / (e_rgbd21.max() - e_rgbd21.min() + 1e-8)
                e_rgbd21 = 255 * e_rgbd21
                filename = os.path.join(self.config.test_folder, name[:-6] + '_edge.png')
                cv2.imwrite(filename, e_rgbd21)'''
        time_e = time.time()
        print('Speed: %f FPS' % (img_num / (time_e - time_s)))
        print('Test Done!')
    
  
    # training phase
    def train(self):
        iter_num = len(self.train_loader.dataset) // self.config.batch_size
        
        loss_vals=  []
        
        for epoch in range(self.config.epoch):
            r_sal_loss = 0
            r_sal_loss_item=0
            for i, data_batch in enumerate(self.train_loader):
                sal_image, sal_depth, sal_label, sal_edge = data_batch['sal_image'], data_batch['sal_depth'], data_batch[
                    'sal_label'], data_batch['sal_edge']
                if (sal_image.size(2) != sal_label.size(2)) or (sal_image.size(3) != sal_label.size(3)):
                    print('IMAGE ERROR, PASSING```')
                    continue
                if self.config.cuda:
                    device = torch.device(self.config.device_id)
                    sal_image, sal_depth, sal_label, sal_edge= sal_image.to(device), sal_depth.to(device), sal_label.to(device),sal_edge.to(device)

               
                self.optimizer.zero_grad()
                sal_label_coarse = F.interpolate(sal_label, size_coarse, mode='bilinear', align_corners=True)
                
                sal_edge_rgbd0,sal_edge_rgbd1,sal_edge_rgbd2 = self.net(sal_image,sal_depth)
                
      
                
                edge_loss_rgbd0= F.binary_cross_entropy_with_logits(sal_edge_rgbd0,sal_label)
                edge_loss_rgbd1= F.binary_cross_entropy_with_logits(sal_edge_rgbd1,sal_label)
                edge_loss_rgbd2= F.binary_cross_entropy_with_logits(sal_edge_rgbd2,sal_label)
                
                sal_loss_fuse = 255*edge_loss_rgbd0+512*edge_loss_rgbd1+1024*edge_loss_rgbd2
                sal_loss = sal_loss_fuse/ (self.iter_size * self.config.batch_size)
                r_sal_loss += sal_loss.data
                r_sal_loss_item+=sal_loss.item() * sal_image.size(0)
                sal_loss.backward()
                self.optimizer.step()

                if (i + 1) % (self.show_every // self.config.batch_size) == 0:
                    print('epoch: [%2d/%2d], iter: [%5d/%5d]  ||  rgb1 : %0.4f  ||rgb2:%0.4f|| edge_loss3:%0.4f' % (
                        epoch, self.config.epoch, i + 1, iter_num, edge_loss_rgbd0,edge_loss_rgbd1,edge_loss_rgbd2))
                    # print('Learning rate: ' + str(self.lr))
                    writer.add_scalar('training loss', r_sal_loss / (self.show_every / self.iter_size),
                                      epoch * len(self.train_loader.dataset) + i)

                    writer.add_scalar('sal_edge training loss', edge_loss_rgbd2.data,
                                      epoch * len(self.train_loader.dataset) + i)

                    r_sal_loss = 0

                    
                    fsal = sal_edge_rgbd0[0].clone()
                    fsal = fsal.sigmoid().data.cpu().numpy().squeeze()
                    fsal = (fsal - fsal.min()) / (fsal.max() - fsal.min() + 1e-8)
                    writer.add_image('sal_final', torch.tensor(fsal), i, dataformats='HW')
                    grid_image = make_grid(sal_label[0].clone().cpu().data, 1, normalize=True)

                    fsal = sal_edge_rgbd1[0].clone()
                    fsal = fsal.sigmoid().data.cpu().numpy().squeeze()
                    fsal = (fsal - fsal.min()) / (fsal.max() - fsal.min() + 1e-8)
                    writer.add_image('sal_final', torch.tensor(fsal), i, dataformats='HW')
                    grid_image = make_grid(sal_label[0].clone().cpu().data, 1, normalize=True)

                   
                    sal_edge_rgbd = sal_edge_rgbd2[0].clone()
                    sal_edge_rgbd = sal_edge_rgbd.sigmoid().data.cpu().numpy().squeeze()
                    sal_edge_rgbd = (sal_edge_rgbd - sal_edge_rgbd.min()) / (sal_edge_rgbd.max() - sal_edge_rgbd.min() + 1e-8)
                    writer.add_image('sal_edge_rgbd', torch.tensor(sal_edge_rgbd), i, dataformats='HW')
                    grid_image = make_grid(sal_edge[0].clone().cpu().data, 1, normalize=True)


            if (epoch + 1) % self.config.epoch_save == 0:
                torch.save(self.net.state_dict(), '%s/epoch_%d.pth' % (self.config.save_folder, epoch + 1))
            train_loss=r_sal_loss_item/len(self.train_loader.dataset)
            loss_vals.append(train_loss)
            
            print('Epoch:[%2d/%2d] | Train Loss : %.3f' % (epoch, self.config.epoch,train_loss))
            
        # save model
        torch.save(self.net.state_dict(), '%s/final.pth' % self.config.save_folder)
        

