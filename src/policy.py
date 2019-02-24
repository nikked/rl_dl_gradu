import tensorflow as tf
import numpy as np

from src.params import (
    TRADING_COST,
    INTEREST_RATE,
    N_FILTER_1,
    N_FILTER_2,
    KERNEL1_SIZE,
    CASH_BIAS_INIT,
    RATIO_REGUL,
    LEARNING_RATE,
)

OPTIMIZER = tf.train.AdamOptimizer(LEARNING_RATE)


# define neural net \pi_\phi(s) as a class


class Policy:  # pylint: disable=too-many-instance-attributes
    """
    This class is used to instanciate the policy network agent

    """

    def __init__(  # pylint: disable=too-many-arguments, too-many-locals, too-many-statements
        self,
        nb_stocks,
        length_tensor,
        sess,
        w_eq,
        nb_feature_map,
        trading_cost=TRADING_COST,
        interest_rate=INTEREST_RATE,
        n_filter_1=N_FILTER_1,
        n_filter_2=N_FILTER_2,
        gpu_device=None,
    ):

        # parameters
        self.trading_cost = trading_cost
        self.interest_rate = interest_rate
        self.n_filter_1 = n_filter_1
        self.n_filter_2 = n_filter_2
        self.length_tensor = length_tensor
        self.nb_stocks = nb_stocks

        if gpu_device:
            self.tf_device = "/device:GPU:{}".format(gpu_device)

        else:
            self.tf_device = "/cpu:0"

        print("Using tf device {}".format(self.tf_device))

        with tf.device(self.tf_device):
            with tf.variable_scope("Inputs"):

                # Placeholder

                # tensor of the prices
                self.x_current = tf.placeholder(
                    tf.float32,
                    [None, nb_feature_map, self.nb_stocks, self.length_tensor],
                )  # The Price tensor
                # weights at the previous time step
                self.w_previous = tf.placeholder(tf.float32, [None, self.nb_stocks + 1])
                # portfolio value at the previous time step
                self.pf_value_previous = tf.placeholder(tf.float32, [None, 1])
                # vector of Open(t+1)/Open(t)
                self.daily_return_t = tf.placeholder(tf.float32, [None, self.nb_stocks])

                # self.pf_value_previous_eq = tf.placeholder(tf.float32, [None, 1])

            with tf.variable_scope("Policy_Model"):

                # variable of the cash bias
                bias = tf.get_variable(
                    "cash_bias",
                    shape=[1, 1, 1, 1],
                    initializer=tf.constant_initializer(CASH_BIAS_INIT),
                )
                # shape of the tensor == batchsize
                shape_x_current = tf.shape(self.x_current)[0]
                # trick to get a "tensor size" for the cash bias
                self.cash_bias = tf.tile(  # pylint: disable=no-member
                    bias, tf.stack([shape_x_current, 1, 1, 1])
                )
                # print(self.cash_bias.shape)

                with tf.variable_scope("Conv1"):
                    # first layer on the x_current tensor
                    # return a tensor of depth 2
                    self.conv1 = tf.layers.conv2d(
                        inputs=tf.transpose(self.x_current, perm=[0, 3, 2, 1]),
                        activation=tf.nn.relu,  # pylint: disable=no-member
                        filters=self.n_filter_1,
                        strides=(1, 1),
                        kernel_size=KERNEL1_SIZE,
                        padding="same",
                    )

                with tf.variable_scope("Conv2"):

                    # feature maps
                    self.conv2 = tf.layers.conv2d(
                        inputs=self.conv1,
                        activation=tf.nn.relu,  # pylint: disable=no-member
                        filters=self.n_filter_2,
                        strides=(self.length_tensor, 1),
                        kernel_size=(1, self.length_tensor),
                        padding="same",
                    )

                with tf.variable_scope("Tensor3"):
                    # w from last periods
                    # trick to have good dimensions
                    w_wo_c = self.w_previous[:, 1:]
                    w_wo_c = tf.expand_dims(w_wo_c, 1)
                    w_wo_c = tf.expand_dims(w_wo_c, -1)
                    self.tensor3 = tf.concat([self.conv2, w_wo_c], axis=3)

                with tf.variable_scope("Conv3"):
                    # last feature map WITHOUT cash bias
                    self.conv3 = tf.layers.conv2d(
                        inputs=self.conv2,
                        activation=tf.nn.relu,  # pylint: disable=no-member
                        filters=1,
                        strides=(self.n_filter_2 + 1, 1),
                        kernel_size=(1, 1),
                        padding="same",
                    )

                with tf.variable_scope("Tensor4"):
                    # last feature map WITH cash bias
                    self.tensor4 = tf.concat([self.cash_bias, self.conv3], axis=2)
                    # we squeeze to reduce and get the good dimension
                    self.squeezed_tensor4 = tf.squeeze(self.tensor4, [1, 3])

                with tf.variable_scope("Policy_Output"):
                    # softmax layer to obtain weights
                    self.action = tf.nn.softmax(self.squeezed_tensor4)

                with tf.variable_scope("Reward"):
                    # computation of the reward
                    # please look at the chronological map to understand
                    constant_return = tf.constant(1 + self.interest_rate, shape=[1, 1])
                    cash_return = tf.tile(  # pylint: disable=no-member
                        constant_return, tf.stack([shape_x_current, 1])
                    )
                    y_t = tf.concat([cash_return, self.daily_return_t], axis=1)
                    v_prime_t = self.action * self.pf_value_previous
                    v_previous = self.w_previous * self.pf_value_previous

                    # this is just a trick to get the good shape for cost
                    constant = tf.constant(1.0, shape=[1])

                    cost = (
                        self.trading_cost
                        * tf.norm(v_prime_t - v_previous, ord=1, axis=1)
                        * constant
                    )

                    cost = tf.expand_dims(cost, 1)

                    zero = tf.constant(
                        np.array([0.0] * self.nb_stocks).reshape(1, self.nb_stocks),
                        shape=[1, self.nb_stocks],
                        dtype=tf.float32,
                    )

                    vec_zero = tf.tile(  #  pylint: disable=no-member
                        zero, tf.stack([shape_x_current, 1])
                    )
                    vec_cost = tf.concat([cost, vec_zero], axis=1)

                    v_second_t = v_prime_t - vec_cost

                    v_t = tf.multiply(v_second_t, y_t)
                    self.portfolio_value = tf.norm(v_t, ord=1)
                    self.instantaneous_reward = (
                        self.portfolio_value - self.pf_value_previous
                    ) / self.pf_value_previous

                with tf.variable_scope("Reward_Equiweighted"):
                    constant_return = tf.constant(1 + self.interest_rate, shape=[1, 1])
                    cash_return = tf.tile(  # pylint: disable=no-member
                        constant_return, tf.stack([shape_x_current, 1])
                    )
                    y_t = tf.concat([cash_return, self.daily_return_t], axis=1)

                    v_eq = w_eq * self.pf_value_previous
                    v_eq_second = tf.multiply(v_eq, y_t)

                    self.portfolio_value_eq = tf.norm(v_eq_second, ord=1)

                    self.instantaneous_reward_eq = (
                        self.portfolio_value_eq - self.pf_value_previous
                    ) / self.pf_value_previous

                with tf.variable_scope("Max_weight"):
                    self.max_weight = tf.reduce_max(self.action)
                    print(self.max_weight.shape)

                with tf.variable_scope("Reward_adjusted"):

                    self.adjested_reward = (
                        self.instantaneous_reward
                        - self.instantaneous_reward_eq
                        - RATIO_REGUL * self.max_weight
                    )

        # objective function
        # maximize reward over the batch
        # min(-r) = max(r)
        with tf.device(self.tf_device):
            self.train_op = OPTIMIZER.minimize(-self.adjested_reward)

        # some bookkeeping
        self.optimizer = OPTIMIZER
        self.sess = sess

    def compute_w(self, x_current, w_previous):
        """
        This function returns the action the agent takes
        given the input tensor and the w_previous

        It is a vector of weight

        """
        with tf.device(self.tf_device):
            return self.sess.run(
                tf.squeeze(self.action),
                feed_dict={self.x_current: x_current, self.w_previous: w_previous},
            )

    def train(self, x_current, w_previous, pf_value_previous, daily_return_t):
        """
        This function trains the neural network
        maximizing the reward
        the input is a batch of the differents values
        """
        with tf.device(self.tf_device):
            self.sess.run(
                self.train_op,
                feed_dict={
                    self.x_current: x_current,
                    self.w_previous: w_previous,
                    self.pf_value_previous: pf_value_previous,
                    self.daily_return_t: daily_return_t,
                },
            )