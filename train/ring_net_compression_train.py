
import os.path
import time

import numpy as np
import tensorflow as tf

import sys
sys.path.append('../')
import model.ring_net as ring_net

FLAGS = tf.app.flags.FLAGS

tf.app.flags.DEFINE_string('train_dir', '../checkpoints/train_store_',
                            """dir to store trained net""")
tf.app.flags.DEFINE_float('input_keep_prob', 1.0,
                          """ input keep probability """)
tf.app.flags.DEFINE_float('keep_prob_encoding', 1.0,
                          """ keep encoding probability """)
tf.app.flags.DEFINE_float('keep_prob_lstm', 1.0,
                          """ keep lstm probability """)
tf.app.flags.DEFINE_float('keep_prob_decoding', 1.0,
                          """ keep decoding probability """)
tf.app.flags.DEFINE_bool('load_network', True,
                          """ whether to load the network or not """)

train_dir = FLAGS.train_dir + FLAGS.model + FLAGS.system + "_compression" + FLAGS.compression_loss + "_compression_vae_loss_" + str(FLAGS.compression_vae_loss) + "_sample_compression_" + str(FLAGS.sample_compression) + "_lstm_size_" + str(FLAGS.lstm_size) + "_num_layers_" + str(FLAGS.num_layers)

CURRICULUM_STEPS = [50000, 50000, 100000]
CURRICULUM_SEQ = [6, 8, 10]
CURRICULUM_BATCH_SIZE = [32, 32, 32]
CURRICULUM_LEARNING_RATE = [1e-4, 1e-4, 1e-4]
CURRICULUM_TRAIN_PIECE = ["all", "all", "all"]

def train(iteration):
  """Train ring_net for a number of steps."""
  with tf.Graph().as_default():
    # make inputs
    x = ring_net.inputs(CURRICULUM_BATCH_SIZE[iteration], CURRICULUM_SEQ[iteration]) 

    # possible input dropout 
    input_keep_prob = tf.placeholder("float")
    x_drop = tf.nn.dropout(x, input_keep_prob)

    # possible dropout inside
    keep_prob_encoding = tf.placeholder("float")
    keep_prob_lstm = tf.placeholder("float")
    keep_prob_decoding = tf.placeholder("float")

    # create and unrap network
    output_f, output_t, output_g, output_autoencoding = ring_net.unwrap(x_drop, keep_prob_encoding, keep_prob_lstm, keep_prob_decoding, CURRICULUM_SEQ[iteration], CURRICULUM_TRAIN_PIECE[iteration]) 

    # calc error
    total_loss = ring_net.loss(x, output_f, output_t, output_g, output_autoencoding, CURRICULUM_TRAIN_PIECE[iteration])
    #loss_vae, loss_reconstruction_autoencoder, loss_reconstruction_g, loss_t = ring_net.loss(x, output_f_mean, output_f_stddev, output_t_mean, output_t_stddev, output_g, output_autoencoding, CURRicULUM_TRAIN_PIECE[iteration])
    #if CURRICULUM_AUTOENCODER[iteration]:
    #  total_loss = tf.reduce_mean(loss_vae + loss_reconstruction_autoencoder)
    #else:
    #  total_loss = tf.reduce_mean(loss_vae + loss_reconstruction_autoencoder + loss_reconstruction_g + loss_t)
    total_loss = tf.div(total_loss, CURRICULUM_SEQ[iteration])

    # train hopefuly 
    train_op = ring_net.train(total_loss, CURRICULUM_LEARNING_RATE[iteration])
    
    # List of all Variables
    variables = tf.all_variables()

    # Build a saver
    saver = tf.train.Saver(tf.all_variables())   

    # Summary op
    summary_op = tf.merge_all_summaries()
 
    # Build an initialization operation to run below.
    if iteration == 0:
      init = tf.initialize_all_variables()

    # Start running operations on the Graph.
    sess = tf.Session()

    # init if this is the very time training
    #if iteration == 0:
    #  print("init network from autoencoder pretrain")
    #  sess.run(init)

    # restore if iteration is not 0
    if FLAGS.load_network:
      variables_to_restore = tf.all_variables()
      autoencoder_variables = [variable for i, variable in enumerate(variables_to_restore) if ("compress" not in variable.name[:variable.name.index(':')]) and ("RNN" not in variable.name[:variable.name.index(':')])]
      rnn_variables = [variable for i, variable in enumerate(variables_to_restore) if ("compress" in variable.name[:variable.name.index(':')]) or ("RNN" in variable.name[:variable.name.index(':')])]
    
      if iteration == 0: 
        print(FLAGS.train_dir + FLAGS.model + FLAGS.system + "_autoencoder")
        ckpt = tf.train.get_checkpoint_state(FLAGS.train_dir + FLAGS.model + FLAGS.system + "_autoencoder")
      else:
        ckpt = tf.train.get_checkpoint_state(train_dir)
      autoencoder_saver = tf.train.Saver(autoencoder_variables)
      print("restoring autoencoder part of network form " + ckpt.model_checkpoint_path)
      autoencoder_saver.restore(sess, ckpt.model_checkpoint_path)
      print("restored file from " + ckpt.model_checkpoint_path)

      if iteration == 0:
        print("init compression part of network from scratch")
        rnn_init = tf.initialize_variables(rnn_variables)
        sess.run(rnn_init)
      else:
        rnn_saver = tf.train.Saver(rnn_variables)
        print("restoring compression part of network")
        rnn_saver.restore(sess, ckpt.model_checkpoint_path)
        print("restored file from " + ckpt.model_checkpoint_path)
 
    # Start que runner
    tf.train.start_queue_runners(sess=sess)

    # Summary op
    graph_def = sess.graph.as_graph_def(add_shapes=True)
    summary_writer = tf.train.SummaryWriter(train_dir, graph_def=graph_def)

    for step in xrange(CURRICULUM_STEPS[iteration]):
      t = time.time()
      _ , loss_r, output_f_g = sess.run([train_op, total_loss, output_f],feed_dict={keep_prob_encoding:FLAGS.keep_prob_encoding, keep_prob_lstm:FLAGS.keep_prob_lstm, keep_prob_decoding:FLAGS.keep_prob_decoding, input_keep_prob:FLAGS.input_keep_prob})
      elapsed = time.time() - t
      #print("loss vae value at " + str(loss_vae_r))
      #print("loss value at " + str(loss_r))
      #print("g " + str(np.max(g_r)))
      #print("g " + str(np.min(g_r)))
      #print("im " + str(np.max(im)))
      #print("im " + str(np.min(im)))
      #print("time per batch is " + str(elapsed))


      if step%100 == 0:
        print("loss value at " + str(loss_r))
        print("time per batch is " + str(elapsed))
        print("max ouput f is ")
        print(np.max(output_f_g))
        print(np.min(output_f_g))
        summary_str = sess.run(summary_op, feed_dict={keep_prob_encoding:FLAGS.keep_prob_encoding, keep_prob_lstm:FLAGS.keep_prob_lstm, keep_prob_decoding:FLAGS.keep_prob_decoding, input_keep_prob:FLAGS.input_keep_prob})
        summary_writer.add_summary(summary_str, step) 
      
      assert not np.isnan(loss_r), 'Model diverged with loss = NaN'

      if step%1000 == 0:
        checkpoint_path = os.path.join(train_dir, 'model.ckpt')
        saver.save(sess, checkpoint_path, global_step=step)  
        print("saved to " + train_dir)

def main(argv=None):  # pylint: disable=unused-argument
  if tf.gfile.Exists(train_dir):
    tf.gfile.DeleteRecursively(train_dir)
  tf.gfile.MakeDirs(train_dir)
  for i in xrange(len(CURRICULUM_STEPS)):
    train(i)

if __name__ == '__main__':
  tf.app.run()
