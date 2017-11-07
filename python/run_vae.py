#!/usr/bin/env python3
import numpy as np
import tensorflow as tf
from datetime import datetime
from optparse import OptionParser
import sys
import os
import warnings

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa
import seaborn as sns  # noqa

sys.path.append('../python/')
from utils import makedirs  # noqa
from train_process import train_model, test_model  # noqa
from train_process import get_fixed_mnist, setup_vaes_and_params  # noqa

np.random.seed(1234)
tf.set_random_seed(1234)
sns.set_style('whitegrid')
sns.set_context(
    'paper',
    font_scale=2.0,
    rc={'lines.linewidth': 2, 'lines.markersize': 10, 'figsize': (5, 4.8)})

tf.logging.set_verbosity(tf.logging.ERROR)
tf.logging.set_verbosity(tf.logging.WARN)
tf.logging.set_verbosity(tf.logging.DEBUG)
tf.logging.set_verbosity(tf.logging.FATAL)

warnings.filterwarnings('ignore', module='matplotlib')


def main():
    parser = OptionParser(usage="usage: %prog [options]",
                          version="%prog 1.0")
    parser.add_option("--n_z", type='int', help="size of stochastic layer")
    parser.add_option("--n_ary", type='int', help="arity of latent variable")
    parser.add_option("--en_dist", type='string', help="encoder distribution")
    parser.add_option("--l_r", type='float', help="learning rate")
    parser.add_option("--n_samples", type='int',
                      help="train objective samples")
    parser.add_option("--test_b_size", type='int', default=1024,
                      help="test batch size")
    parser.add_option("--test_n_samples", type='int', default=5,
                      help="test objective samples")
    parser.add_option("--c_devs", type='string', help="cuda devices")
    parser.add_option("--mem_frac", type='float', default=0.5,
                      help="memory fraction used in gpu")
    parser.add_option("--mode", type='string', default='train',
                      help='train or test')
    (options, args) = parser.parse_args()
    options_to_str = ['{}{}'.format(k, v) for k, v in vars(options).items()]
    logging_file = '-'.join(sorted(options_to_str))
    logging_file += datetime.now().strftime("_%H:%M:%S") + '.txt'
    log_dir = os.path.join('logs', datetime.now().strftime("%Y-%m-%d"))
    makedirs(log_dir)
    logging_path = os.path.join(log_dir, logging_file)

    mnist = get_fixed_mnist('datasets/',
                            validation_size=10000)
    X_train, X_val, X_test = mnist.train, mnist.validation, mnist.test

    params = {
        'X_train': X_train,
        'X_test': X_test,
        'X_val': X_val,
        'dataset': 'BinaryMNIST',
        'n_z': options.n_z,
        'n_ary': options.n_ary,
        'encoder_distribution': options.en_dist,
        'learning_rate': options.l_r,
        'train_batch_size': 128,
        'train_obj_samples': options.n_samples,
        'val_batch_size': 1024,
        'val_obj_samples': 5,
        'test_batch_size': options.test_b_size,
        'test_obj_samples': options.test_n_samples,
        'cuda_devices': options.c_devs,
        'save_step': 100,
        'n_epochs': 3001,
        'save_weights': True,
        'mem_fraction': options.mem_frac,
        'all_vaes': True,
        'mode': options.mode,
        'results_dir': 'test_results',
        'logging_path': logging_path
    }
    if options.mode == 'train':
        train_model(**setup_vaes_and_params(**params))
    else:
        test_model(**setup_vaes_and_params(**params))


if __name__ == '__main__':
    main()
