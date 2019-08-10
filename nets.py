import numpy as np
import tensorflow as tf


def nn_layer(x, size, activation=tf.nn.relu, drop_out=0.3, use_bias=True, return_vars=True):
    # x*W+b
    if drop_out:
        x = tf.nn.dropout(x, rate=drop_out)

    W = tf.Variable(np.random.random((x.shape[1], size)) * (1. / (int(x.shape[1]) * size)))

    if use_bias:
        b = tf.Variable(np.random.random((1, size)) * (1. / size))
        line = tf.matmul(x, W) + b
    else:
        b = None
        line = tf.matmul(x, W)

    if activation is None:
        y = line
    else:
        y = activation(line)

    if return_vars:
        return y, W, b
    else:
        return y


class FullyConnectedDNN:

    def __init__(self, input_dims, output_dims, hidden_layers=[200, 100], activations=[tf.nn.relu, tf.nn.relu], use_biases=[True, True],
                 drop_out=.3, output_activation=None, output_use_bias=False, lr=1e-2):

        self.input_dims = input_dims
        self.output_dims = output_dims

        self.input_shape = tuple([self.input_dims])
        self.output_shape = tuple([self.output_dims])

        layers = np.append(hidden_layers, output_dims).astype(np.int) if hidden_layers is not None else np.array([output_dims])
        all_activations = activations.copy() if activations is not None else []
        all_activations.append(output_activation)
        all_use_biases = use_biases.copy() if use_biases is not None else []
        all_use_biases.append(output_use_bias)

        print("NN: layers:{}, activations:{}".format(layers, all_activations, all_use_biases))

        self.ys, self.Ws, self.bs = [], [], []

        # tf.compat.v1.reset_default_graph()
        self.x = tf.compat.v1.placeholder(tf.float64, shape=(None, input_dims))
        x = self.x
        for i, layer in enumerate(layers):
            y, W, b = nn_layer(x, layer, all_activations[i], drop_out=drop_out if i > 0 else 0., use_bias=all_use_biases[i], return_vars=True)

            self.ys.append(y)
            self.Ws.append(W)
            self.bs.append(b)

            x = y

        self.y = y

        self.y_ = tf.compat.v1.placeholder(tf.float64, shape=(None, output_dims))

        self.loss = tf.compat.v1.losses.mean_squared_error(self.y_, self.y)
        # self.loss = tf.reduce_mean(tf.squared_difference(self.y_, self.y))

        self.train = tf.compat.v1.train.AdamOptimizer(lr).minimize(self.loss)

        self.init_op = tf.compat.v1.global_variables_initializer()

        self.sess = tf.compat.v1.Session()
        self.sess.run(self.init_op)

    def predict(self, X):

        X = np.atleast_2d(X)

        result = self.sess.run(self.y, feed_dict={
                self.x: X
        })

        return result

    def fit(self, X, y):

        assert X.shape[0] == y.shape[0],\
            'X.shape[0] != y.shape[0], {} != {}'.format(X.shape[0], y.shape[0])

        assert X.shape[1] == self.input_shape[0],\
            'X.shape[1] = {}, it should be {}'.format(X.shape, self.input_shape)
        assert y.shape[1] == self.output_shape[0],\
            'y.shape[1] = {}, it should be {}'.format(y.shape, self.output_shape)

        self.sess.run(self.train, feed_dict={
                self.x : X,
                self.y_: y
        })

    def partial_fit(self, X, y):
        self.fit(np.atleast_2d(X), np.atleast_2d(y))


class PolicyModel(FullyConnectedDNN):

    def __init__(self, input_dims, output_dims, gamma=.99, lr=1e-2, **kwargs):
        super().__init__(input_dims, output_dims, **kwargs, output_activation=tf.nn.softmax, output_use_bias=False)

        self.gamma = gamma

        gammas_n = 1000
        self.GAMMAS = np.power(gamma*np.ones(gammas_n), np.arange(gammas_n, 0, -1)-1)

        self.pi_s = self.y

        self.actions = tf.placeholder(tf.int64, shape=(None,))
        self.rewards = tf.placeholder(tf.float64, shape=(None,))
        self.gammas = tf.placeholder(tf.float64, shape=(None,))
        self.vs = tf.placeholder(tf.float64, shape=(None,))

        self.pi_s_a = tf.reduce_sum(self.pi_s*tf.one_hot(self.actions, self.output_dims, dtype=tf.float64), axis=1)

        self.advantages = self.gammas*self.rewards-self.vs

        self.loss = -tf.reduce_sum(self.advantages*tf.log(self.pi_s_a))

        self.train = tf.compat.v1.train.AdamOptimizer(lr).minimize(self.loss)

        self.sess.run(tf.compat.v1.global_variables_initializer())

    def policy(self, states, actions=None):
        states = np.atleast_2d(states)

        assert states.shape[1] == self.input_dims

        if actions is None:
            result = self.sess.run(self.pi_s, feed_dict={
                    self.x: states
            })
            assert result.shape[1] == self.output_dims
        else:
            actions = np.atleast_1d(actions)
            result = self.sess.run(self.pi_s_a, feed_dict={
                    self.x: states,
                    self.actions: actions
            })
            assert len(result.shape) == 1

        assert result.shape[0] == states.shape[0]

        return result

    def full_episode_update(self, states, actions, rewards, vs):
        states = np.atleast_2d(states)
        actions = np.atleast_1d(actions)
        rewards = np.atleast_1d(rewards)
        vs = np.atleast_1d(vs)

        size = len(states)
        assert len(actions) == size, '{} != {}'.format(len(actions), size)
        assert len(rewards) == size, '{} != {}'.format(len(rewards), size)
        assert len(vs) == size, '{} != {}'.format(len(vs), size)

        self.sess.run(self.train, feed_dict={self.x: states,
                                             self.actions: actions,
                                             self.gammas: self.GAMMAS[-size:],
                                             self.rewards: rewards,
                                             self.vs: vs
                                             })

    def td_update(self, state, action, reward, v):
        raise NotImplementedError


class CriticModel(FullyConnectedDNN):

    def __init__(self, state_dims, action_dims, **kwargs):
        self.state_dims = state_dims
        self.action_dims 
        super().__init__(input_dims=input_dims, output_dims=1, **kwargs)

    def value(self, states):
        states = np.atleast_2d(states)

        assert states.shape[1] == self.input_dims

        return self.predict(states).flatten()

    def full_episode_update(self, states, rewards):

        states = np.atleast_2d(states)
        rewards = np.reshape(rewards, (-1, 1))

        size = len(states)
        assert len(rewards) == size, '{} != {}'.format(len(rewards), size)

        self.fit(states, rewards)

    def td_update(self, state, reward):
        raise NotImplementedError
