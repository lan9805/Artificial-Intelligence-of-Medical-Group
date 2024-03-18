import os
import torch
from torch import nn
from torch.utils.data import DataLoader
from get_data import Clinical_Dataset
from models.get_net import get_mlp
from tqdm import tqdm
from tensorboardX import SummaryWriter
from utils.config import opt

def train(net:nn.Module, train_iter:DataLoader, valid_iter:DataLoader, opt:object, loss:nn, optimizer:torch.optim):
    '''
    实验室检查数据分类模型训练函数

    args:
        net(nn.Module): 待训练的网络
        train_iter(DataLoader): 训练集
        valid_iter(DataLoader): 验证集
        opt(object): 配置文件中的参数信息
        loss(nn): 损失函数
        optimizer(torch.optim):优化器
    '''

    # 创建权重保存路径与log信息保存路径
    if not os.path.exists(opt.clinical_weight_dir):
        os.mkdir(opt.clinical_weight_dir)
    if not os.path.exists(opt.clinical_log_dir):
        os.mkdir(opt.clinical_log_dir)

    # 设置log信息写入器
    writer = SummaryWriter(log_dir=opt.clinical_log_dir)

    print('Training on', opt.device)
    net.to(opt.device)

    min_val_loss = torch.inf

    for epoch in range(opt.clinical_epoch):
        net.train()
        train_loss, train_num, train_acc = 0, 0, 0
        n_y = 0
        for X, y in tqdm(train_iter, 'train epoch:'+str(epoch)):
            optimizer.zero_grad()
            X, y = X.to(opt.device), y.to(opt.device)
            y_hat = net(X)
            l = loss(y_hat, y)
            l.backward()
            optimizer.step()

            train_num += 1
            train_loss += l
            n_y += y.shape[0]
            y_hat = nn.Softmax(dim=1)(y_hat)
            pred = torch.argmax(y_hat, dim=1)
            acc = (pred == y).sum()
            train_acc += float(acc)
        train_loss /= train_num
        train_acc /= n_y

        # 记录训练信息
        writer.add_scalar('data/train_loss_epoch', train_loss, epoch)
        writer.add_scalar('data/train_acc_epoch', train_acc, epoch)
        print('epoch:%f loss:%f acc:%f' % (epoch, train_loss, train_acc))

        # 网络验证
        net.eval()
        valid_loss, valid_num, valid_acc = 0, 0, 0
        n_y = 0
        for X, y in tqdm(valid_iter, 'valid epoch:'+str(epoch)):
            X, y = X.to(opt.device), y.to(opt.device)
            with torch.no_grad():
                y_hat = net(X)
                l = loss(y_hat, y)

                valid_num += 1
                valid_loss += l
                n_y += y.shape[0]
                y_hat = nn.Softmax(dim=1)(y_hat)
                pred = torch.argmax(y_hat, dim=1)
                acc = (pred == y).sum()
                valid_acc += float(acc)
        valid_loss /= valid_num
        valid_acc /= n_y
        
        # 记录训练信息
        writer.add_scalar('data/valid_loss_epoch', valid_loss, epoch)
        writer.add_scalar('data/valid_acc_epoch', valid_acc, epoch)
        print('epoch:%d loss:%f acc:%f' % (epoch, valid_loss, valid_acc))

        # 若当前的alid loss 比最低的loss低, 则保存当前权重
        if min_val_loss > valid_loss:
            print(f'valid loss imporved from {min_val_loss} to {valid_loss}')
            min_val_loss = valid_loss
            best_weight_dir = os.path.join(opt.clinical_weight_dir, 'clinical_model' + '.pth.tar')
            torch.save({'state dict' : net.state_dict()}, best_weight_dir)
            print(f'save model at {best_weight_dir}')
        else:
            print(f'valid loss did not improve! The lowest loss is {min_val_loss}')
        
        torch.cuda.empty_cache()

    print(f'finish!, valid loss {min_val_loss}')

def xavier_init_weights(m):
    if type(m) == nn.Linear:
        nn.init.xavier_uniform_(m.weight)

if __name__ == "__main__":
    train_set = Clinical_Dataset(opt, opt.data_set_path, opt.train_set_path)
    valid_set = Clinical_Dataset(opt, opt.data_set_path, opt.valid_set_path)

    train_iter = DataLoader(train_set, batch_size=opt.clinical_batch_size, shuffle=True)
    valid_iter = DataLoader(valid_set, batch_size=opt.clinical_batch_size, shuffle=False)

    net = get_mlp(opt, False)

    net.apply(xavier_init_weights)
    
    loss = nn.CrossEntropyLoss()

    optim = torch.optim.SGD(net.parameters(), lr=opt.clinical_lr)

    train(net, train_iter, valid_iter, opt, loss, optim)