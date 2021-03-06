#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Python version: 3.6


import os
import copy
import time
import pickle
import numpy as np
from tqdm import tqdm

import torch
from tensorboardX import SummaryWriter

from options import args_parser
from update import LocalUpdate, test_inference
from models import MLP, CNNMnist, CNNFashion_Mnist, CNNCifar
from utils import get_dataset, average_weights, exp_details


if __name__ == '__main__':
    start_time = time.time()

    # define paths
    path_project = os.path.abspath('..')
    logger = SummaryWriter('../logs')

    args = args_parser()
    exp_details(args)

    if args.gpu:
        torch.cuda.set_device(args.gpu)
    device = 'cuda' if args.gpu else 'cpu'

    # load dataset and user groups
    train_dataset, test_dataset, user_groups, user_groups_test_1, user_groups_test_2 = get_dataset(args)

    # BUILD MODEL
    if args.model == 'cnn':
        # Convolutional neural netork
        if args.dataset == 'mnist':
            global_model = CNNMnist(args=args)
        elif args.dataset == 'fmnist':
            global_model = CNNFashion_Mnist(args=args)
        elif args.dataset == 'cifar':
            global_model = CNNCifar(args=args)

    elif args.model == 'mlp':
        # Multi-layer preceptron
        img_size = train_dataset[0][0].shape
        len_in = 1
        for x in img_size:
            len_in *= x
            global_model = MLP(dim_in=len_in, dim_hidden=64,
                               dim_out=args.num_classes)
    else:
        exit('Error: unrecognized model')

    # Set the model to train and send it to device.
    global_model.to(device)
    global_model.train()
    print(global_model)

    # copy weights
    global_weights = global_model.state_dict()

    # Calculate avg training accuracy over all users at every epoch
    list_acc_1, list_loss_1, list_acc_2, list_loss_2 = [], [], [], []

    # Training
    train_loss, test_accuracy, test_loss = [], [], []
    val_acc_list, net_list = [], []
    cv_loss, cv_acc = [], []
    print_every = 2
    val_loss_pre, counter = 0, 0

    for epoch in tqdm(range(args.epochs)):
        local_weights, local_losses = [], []
        print(f'\n | Global Training Round : {epoch+1} |\n')

        # global_model.train()
        m = max(int(args.frac * args.num_users), 1)
        # idxs_users = np.random.choice(range(args.num_users), m, replace=False) # random client federated
        
        for idx in range(args.num_users):
        # for idx in idxs_users:  # random client federated
            local_model = LocalUpdate(args=args, dataset=train_dataset,
                                      idxs=user_groups[idx], logger=logger)
            w, loss = local_model.update_weights(
                model=copy.deepcopy(global_model), global_round=epoch)
            local_weights.append(copy.deepcopy(w))
            local_losses.append(copy.deepcopy(loss))

        # update global weights
        global_weights = average_weights(local_weights)

        # update global weights
        global_model.load_state_dict(global_weights)
        # global_model.load_state_dict(local_weights[0])
        loss_avg = sum(local_losses) / len(local_losses)
        train_loss.append(loss_avg)

        # global_model.eval()
        # for c in range(args.num_users):
        test_model_1 = LocalUpdate(args=args, dataset=test_dataset,
                                      idxs=user_groups_test_1[0], logger=logger)
        test_model_2 = LocalUpdate(args=args, dataset=test_dataset,
                                      idxs=user_groups_test_2[0], logger=logger)
        acc_1, loss_1 = test_model_1.inference(model=copy.deepcopy(global_model))
        acc_2, loss_2 = test_model_2.inference(model=copy.deepcopy(global_model))
        # acc_1, loss_1 = test_inference(args, copy.deepcopy(global_model), test_dataset, user_groups_test_1)
        # acc_2, loss_2 = test_inference(args, copy.deepcopy(global_model), test_dataset, user_groups_test_2)
        list_acc_1.append(acc_1)
        list_loss_1.append(loss_1)
        list_acc_2.append(acc_2)
        list_loss_2.append(loss_2)
        # test_accuracy.append(sum(list_acc)/len(list_acc))
        # test_accuracy.append(list_acc)
        # test_loss.append(list_loss)
        # print global training loss after every 'i' rounds
        if (epoch+1) % print_every == 0:
            print(f' \nAvg Training Stats after {epoch+1} global rounds:')
            print(f'Training Loss : {np.mean(np.array(train_loss))}')
            print('Train Accuracy: {:.2f}% \n'.format(100*list_acc_1[-1]))
            print('Train Accuracy: {:.2f}% \n'.format(100*list_acc_2[-1]))

    # Test inference after completion of training
    # test_acc, test_loss = test_inference(args, global_model, test_dataset)

    # print(f' \n Results after {args.epochs} global rounds of training:')
    # print("|---- Avg Train Accuracy: {:.2f}%".format(100*test_accuracy[-1]))
    # print("|---- Test Accuracy: {:.2f}%".format(100*test_acc))
    # print("|-------  Loss -------:".format(test_loss))

    # Saving the objects train_loss and test_accuracy:
    file_name = '/home/test_2/Federated-Learning-PyTorch/save/objects/{}_{}_{}_C[{}]_iid[{}]_E[{}]_B[{}].pkl'.\
        format(args.dataset, args.model, args.epochs, args.frac, args.iid,
               args.local_ep, args.local_bs)

    with open(file_name, 'wb') as f:
        pickle.dump([train_loss, list_loss_1, list_acc_1, list_loss_2, list_acc_2], f)

    print('\n Total Run Time: {0:0.4f}'.format(time.time()-start_time))

    # PLOTTING (optional)
    import matplotlib
    import matplotlib.pyplot as plt
    matplotlib.use('Agg')

    # Plot Loss curve
    plt.figure()
    plt.title('Training Loss vs Communication rounds')
    plt.plot(range(len(train_loss)), train_loss, color='r', label = "train_loss")
    plt.plot(range(len(list_loss_1)), list_loss_1, color='m', label = "d1_loss")
    plt.plot(range(len(list_loss_2)), list_loss_2, color='c', label = "d2_loss")
    plt.legend()
    plt.ylabel('Training loss')
    plt.xlabel('Communication Rounds')
    plt.savefig('/home/test_2/Federated-Learning-PyTorch/save/fed_{}_{}_{}_C[{}]_iid[{}]_E[{}]_B[{}]_loss.png'.
                format(args.dataset, args.model, args.epochs, args.frac,
                       args.iid, args.local_ep, args.local_bs))

    # Plot Average Accuracy vs Communication rounds
    plt.figure()
    plt.title('Average Accuracy vs Communication rounds')
    plt.plot(range(len(list_acc_1)), list_acc_1, color='m', label = "d1_acc")
    plt.plot(range(len(list_acc_2)), list_acc_2, color='r', label = "d2_acc")
    plt.ylabel('Average Accuracy')
    plt.xlabel('Communication Rounds')
    plt.savefig('/home/test_2/Federated-Learning-PyTorch/save/fed_{}_{}_{}_C[{}]_iid[{}]_E[{}]_B[{}]_acc.png'.
                format(args.dataset, args.model, args.epochs, args.frac,
                       args.iid, args.local_ep, args.local_bs))
