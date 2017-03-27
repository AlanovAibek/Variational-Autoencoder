import numpy as np
import tensorflow as tf

from utils import *
from itertools import chain

class VAE(object):
    def __init__(self, n_input, n_z, network_architecture, decoder_distribution, learning_rate):
        self.n_input = n_input
        self.n_z = n_z
        self.network_architecture = network_architecture
        self.decoder_distribution = decoder_distribution
        self.learning_rate = learning_rate
        
        self.x = tf.placeholder(tf.float32, [None, n_input])
        self.x_binarized = tf.cast(tf.random_uniform(tf.shape(self.x)) <= self.x, tf.float32)
        self.n_x = tf.cast(tf.shape(self.x)[1], tf.float32)
        
        self._create_network()
        
        self._create_loss_optimizer()
        
        self.init = tf.global_variables_initializer()
        self.saver = tf.train.Saver(self.flat_weights, max_to_keep=None)
        
        self.sess = tf.Session()
        self.sess.run(self.init)
        
    def _create_network(self):
        self.weights = self._initialize_weights(**self.network_architecture)
        self._create_encoder_part()
        self._create_decoder_part()
    
    def _create_encoder_part(self):
        weights = self.weights
        x = self.x_binarized
        
        encoder_layer1 = build_layer(x, *weights['encoder']['h1'], nonlinearity=tf.nn.softplus)
        encoder_layer2 = build_layer(encoder_layer1, *weights['encoder']['h2'], nonlinearity=tf.nn.softplus)
        self.z_mean = build_layer(encoder_layer2, *weights['encoder']['out_mean'])
        self.z_log_sigma_sq = build_layer(encoder_layer2, *weights['encoder']['out_log_sigma_sq'])
        
        epsilon = tf.random_normal((tf.shape(self.x)[0], self.n_z), 0, 1, dtype=tf.float32)
        self.z = self.z_mean + tf.exp(0.5 * self.z_log_sigma_sq) * epsilon
    
    def _create_decoder_part(self):
        weights = self.weights
        decoder_layer1 = build_layer(self.z, *weights['decoder']['h1'], nonlinearity=tf.nn.softplus)
        decoder_layer2 = build_layer(decoder_layer1, *weights['decoder']['h2'], nonlinearity=tf.nn.softplus)
        self.x_reconst = build_layer(decoder_layer2, *weights['decoder']['out_mean'], nonlinearity=tf.nn.sigmoid)
        
    def _initialize_weights(self, n_hidden_encoder_1, n_hidden_encoder_2, 
                           n_hidden_decoder_1, n_hidden_decoder_2):
        weights = dict()
        weights['encoder'] = {
            'h1': init_layer(self.n_input, n_hidden_encoder_1, name='encoder_h1'), 
            'h2': init_layer(n_hidden_encoder_1, n_hidden_encoder_2, name='encoder_h2'), 
            'out_mean': init_layer(n_hidden_encoder_2, self.n_z, name='encoder_out_mean'), 
            'out_log_sigma_sq': init_layer(n_hidden_encoder_2, self.n_z, name='encoder_out_log_sigma_sq')
        }
        self.encoder_weights = list(chain.from_iterable(weights['encoder'].values()))
        weights['decoder'] = {
            'h1': init_layer(self.n_z, n_hidden_decoder_1, name='decoder_h1'), 
            'h2': init_layer(n_hidden_decoder_1, n_hidden_decoder_2, name='decoder_h2'),
            'out_mean': init_layer(n_hidden_decoder_2, self.n_input, name='decoder_out_mean')
        }
        self.decoder_weights = list(chain.from_iterable(weights['decoder'].values()))
        self.flat_weights = flatten(weights)
        return weights
    
    def _create_loss_optimizer(self):
        self._create_loss()
        self._create_optimizer()
    
    def _create_loss(self):
        if self.decoder_distribution == 'gaussian':
            self.decoder_log_density = log_normal_density(self.x_reconst, self.x, 1)
        elif self.decoder_distribution == 'bernoulli':
            self.decoder_log_density = bernoulli_logit_density(self.x, self.x_reconst)
        else:
            raise ValueError('Unsupported decoder distribution!')
            
        self.encoder_log_density = log_normal_density(self.z, self.z_mean, tf.exp(0.5 * self.z_log_sigma_sq))
            
        self.kl_divergency = kl_divergency(self.z_mean, tf.exp(0.5 * self.z_log_sigma_sq))
        
        self.cost_for_decoder_weights = tf.reduce_mean(self.kl_divergency - self.decoder_log_density)
        self.cost_for_encoder_weights = tf.reduce_mean(self.kl_divergency - self.decoder_log_density)
        
        self.cost_for_display = tf.reduce_mean(self.kl_divergency - self.decoder_log_density)
        
    def _create_optimizer(self):
        self.decoder_optimizer = tf.train.AdamOptimizer(learning_rate=self.learning_rate)
        self.decoder_minimizer = self.decoder_optimizer.minimize(self.cost_for_decoder_weights, 
                                                                 var_list=self.decoder_weights)
        
        self.encoder_optimizer = tf.train.AdamOptimizer(learning_rate=self.learning_rate)
        self.encoder_minimizer = self.encoder_optimizer.minimize(self.cost_for_encoder_weights, 
                                                                 var_list=self.encoder_weights)
        
        self.optimizer = tf.train.AdamOptimizer(learning_rate=self.learning_rate)
        self.decoder_gradients = self.optimizer.compute_gradients(self.cost_for_decoder_weights, 
                                                                  var_list=self.decoder_weights)
        self.encoder_gradients = self.optimizer.compute_gradients(self.cost_for_encoder_weights, 
                                                                  var_list=self.encoder_weights)
        
    def partial_fit(self, X):
        self.sess.run(self.decoder_minimizer, feed_dict={self.x: X})
        self.sess.run(self.encoder_minimizer, feed_dict={self.x: X})
    
    def get_decoder_gradients(self, X):
        gradients = self.sess.run(self.decoder_gradients, feed_dict={self.x: X})
        flat_gradients = np.array([])
        for grad in gradients:
            flat_gradients = np.append(flat_gradients, grad[0].flatten())
        return flat_gradients
    
    def get_encoder_gradients(self, X):
        gradients = self.sess.run(self.encoder_gradients, feed_dict={self.x: X})
        flat_gradients = np.array([])
        for grad in gradients:
            flat_gradients = np.append(flat_gradients, grad[0].flatten())
        return flat_gradients
    
    def get_decoder_log_density(self, X):
        return self.sess.run(tf.reduce_mean(self.decoder_log_density), feed_dict={self.x: X})
    
    def transform(self, X):
        return self.sess.run(self.z_mean, feed_dict={self.x: X})
    
    def generate(self, z=None):
        if z is None:
            z = np.random.normal(size=self.n_z)
        return self.sess.run(self.x_reconst, feed_dict={self.z: z})
    
    def reconstruct(self, X):
        return self.sess.run(self.x_reconst, feed_dict={self.x: X})
    
    def loss(self, X):
        return self.sess.run(self.cost_for_display, feed_dict={self.x: X})
    
    def save_weights(self, save_path):
        self.saver.save(self.sess, save_path)
        
    def restore_weights(self, restore_path):
        self.saver.restore(self.sess, restore_path)
    
    def close(self):
        self.sess.close()

class LogDerTrickVAE(VAE):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self._create_network2()
        
        self._create_loss_optimizer2()
        
        self.init = tf.global_variables_initializer()
        self.sess.run(self.init)
        
    def _create_network2(self):
        self.z = tf.stop_gradient(self.z)
        self._create_decoder_part()
    
    def _create_loss_optimizer2(self):
        self._create_loss()
        self.log_der_trick_cost = - self.encoder_log_density * self.decoder_log_density
        self.cost_for_encoder_weights = tf.reduce_mean(self.kl_divergency + self.log_der_trick_cost)
        self._create_optimizer()

class MonteKarloVAE(VAE):
    def __init__(self, *args, n_monte_karlo_samples=10, **kwargs):
        super().__init__(*args, **kwargs)
        self.n_monte_karlo_samples = n_monte_karlo_samples
        
        self._create_network2()
        
        self._create_loss_optimizer2()
        
        self.init = tf.global_variables_initializer()
        self.sess.run(self.init)
        
    def _create_network2(self):
        self.z = tf.stop_gradient(self.z)
        self._create_decoder_part()
        
        self.z_mean_monte_karlo = self.z_mean
        self.z_mean_monte_karlo = tf.tile(tf.reshape(self.z_mean_monte_karlo, [-1]), [self.n_monte_karlo_samples])
        self.z_mean_monte_karlo = tf.reshape(self.z_mean_monte_karlo, [self.n_monte_karlo_samples, -1, self.n_z])

        self.z_log_sigma_sq_monte_karlo = self.z_log_sigma_sq
        self.z_log_sigma_sq_monte_karlo = tf.tile(tf.reshape(self.z_log_sigma_sq_monte_karlo, [-1]), 
                                                  [self.n_monte_karlo_samples])
        self.z_log_sigma_sq_monte_karlo = tf.reshape(self.z_log_sigma_sq_monte_karlo, 
                                                     [self.n_monte_karlo_samples, -1, self.n_z])
        self.z_monte_karlo = tf.random_normal((self.n_monte_karlo_samples, tf.shape(self.x)[0], self.n_z), 
                                              self.z_mean, tf.sqrt(tf.exp(self.z_log_sigma_sq)), dtype=tf.float32)
        self.z_monte_karlo = tf.reshape(self.z_monte_karlo, 
                                        [self.n_monte_karlo_samples*tf.shape(self.x)[0], self.n_z])

        decoder_layer1_monte_karlo = build_layer(self.z_monte_karlo, *self.weights['decoder']['h1'], 
                                                 nonlinearity=tf.nn.softplus)
        decoder_layer2_monte_karlo = build_layer(decoder_layer1_monte_karlo, *self.weights['decoder']['h2'], 
                                                 nonlinearity=tf.nn.softplus)
        self.x_reconst_monte_karlo = build_layer(decoder_layer2_monte_karlo, *self.weights['decoder']['out_mean'], 
                                                 nonlinearity=tf.nn.sigmoid)
        self.x_reconst_monte_karlo = tf.reshape(self.x_reconst_monte_karlo, 
                                                [self.n_monte_karlo_samples, tf.shape(self.x)[0], self.n_input])
    
    def _create_loss_optimizer2(self):
        self._create_loss()
        self.x_repeated = tf.tile(tf.reshape(self.x, [-1]), [self.n_monte_karlo_samples])
        self.x_repeated = tf.reshape(self.x_repeated, [self.n_monte_karlo_samples, -1, self.n_input])
        self.decoder_log_density_monte_karlo = bernoulli_logit_density(self.x_repeated, 
                                                                       self.x_reconst_monte_karlo)
        self.decoder_log_density_monte_karlo = tf.reduce_mean(self.decoder_log_density_monte_karlo, 0)
        self.decoder_log_density_monte_karlo = tf.stop_gradient(self.decoder_log_density_monte_karlo)
        
        self.decoder_log_density_monte_karlo = self.decoder_log_density - self.decoder_log_density_monte_karlo
        self.monte_karlo_cost = - self.encoder_log_density * self.decoder_log_density_monte_karlo
        self.cost_for_encoder_weights = tf.reduce_mean(self.kl_divergency + self.monte_karlo_cost)
        
        self._create_optimizer()