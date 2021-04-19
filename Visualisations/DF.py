import torch
import numpy as np
import os
import cv2
from tensorboardX import SummaryWriter
import shutil


class DeepFeatures(torch.nn.Module):
    '''
    This class extracts, reads, and writes data embeddings using a pretrained deep neural network. Meant to work with
    Tensorboard's Embedding Viewer (https://www.tensorflow.org/tensorboard/tensorboard_projector_plugin).
    When using with a 3 channel image input and a pretrained model from torchvision.models please use the
    following pre-processing pipeline:

    transforms.Compose([transforms.Resize(imsize),
                                     transforms.ToTensor(),
                                     transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225])]) ## As per torchvision docs

    Args:
        model (nn.Module): A Pytorch model that returns an (B,1) embedding for a length B batched input
        imgs_folder (str): The folder path where the input data elements should be written to
        embs_folder (str): The folder path where the output embeddings should be written to
        tensorboard_folder (str): The folder path where the resulting Tensorboard log should be written to
        experiment_name (str): The name of the experiment to use as the log name


    '''

    def __init__(self, model,
                 imgs_folder,
                 embs_folder,
                 tensorboard_folder,
                 experiment_name=None):

        super(DeepFeatures, self).__init__()

        self.step = 0

        self.model = model
        self.model.eval()

        self.imgs_folder = imgs_folder
        self.embs_folder = embs_folder
        self.tensorboard_folder = tensorboard_folder

        self.name = experiment_name

        self.writer = None

        if len(os.listdir(self.imgs_folder)) != 0:
            "Images folder must be empty"
            clear_folder(self.imgs_folder)


        if len(os.listdir(self.embs_folder)) != 0:
            "Embeddings folder must be empty"
            clear_folder(self.embs_folder)

    def generate_embeddings(self, x):
        '''
        Generate embeddings for an input batched tensor

        Args:
            x (torch.Tensor) : A batched pytorch tensor

        Returns:
            (torch.Tensor): The output of self.model against x
        '''
        return (self.model(x))

    def write_embeddings(self, x,labels, outsize=(28, 28)):
        '''
        Generate embeddings for an input batched tensor and write inputs and
        embeddings to self.imgs_folder and self.embs_folder respectively.

        Inputs and outputs will be stored in .npy format with randomly generated
        matching filenames for retrieval

        Args:
            x (torch.Tensor) : An input batched tensor that can be consumed by self.model
            outsize (tuple(int, int)) : A tuple indicating the size that input data arrays should be
            written out to

        Returns:
            (bool) : True if writing was succesful

        '''



        # Generate embeddings
        embs = self.generate_embeddings(x)

        # Detach from graph
        embs = embs.detach().cpu().numpy()

        # Start writing to output folders
        for i in range(len(embs)):
            key = labels[i]
            np.save(self.imgs_folder + r"/" + key + '.npy', tensor2np(x[i], outsize))
            np.save(self.embs_folder + r"/" + key + '.npy', embs[i])

        return (True)

    def _create_writer(self, name):
        '''
        Create a TensorboardX writer object given an experiment name and assigns it to self.writer

        Args:
            name (str): Optional, an experiment name for the writer, defaults to self.name

        Returns:
            (bool): True if writer was created succesfully

        '''

        if self.name is None:
            name = 'Experiment_' + str(np.random.random())
        else:
            name = self.name

        dir_name = os.path.join(self.tensorboard_folder,
                                name)

        if not os.path.exists(dir_name):
            os.mkdir(dir_name)

        else:
            print("Warning: logfile already exists")
            print("logging directory: " + str(dir_name))

        logdir = dir_name
        self.writer = SummaryWriter(logdir=logdir)
        return (True)

    def create_tensorboard_log(self, img_names):

        '''
        Write all images and embeddings from imgs_folder and embs_folder into a tensorboard log
        '''

        if self.writer is None:
            self._create_writer(self.name)



        ## Read in
        all_embeddings = [np.load(os.path.join(self.embs_folder, p)) for p in os.listdir(self.embs_folder) if
                          p.endswith('.npy') and p.replace(".npy", "") in img_names]
        all_images = [np.load(os.path.join(self.imgs_folder, p)) for p in os.listdir(self.imgs_folder) if
                      p.endswith('.npy') and p.replace(".npy", "") in img_names]
        all_images = [np.moveaxis(a, 2, 0) for a in all_images]  # (HWC) -> (CHW)

        ## Stack into tensors
        all_embeddings = torch.Tensor(all_embeddings)
        all_images = torch.Tensor(all_images)

        print(all_embeddings.shape)
        print(all_images.shape)
        img_names = [name[:-2] for name in img_names]
        self.writer.add_embedding(all_embeddings,metadata = img_names,  label_img=all_images, global_step = self.step)
        self.step += 1


def tensor2np(tensor, resize_to=None):
    '''
    Convert an image tensor to a numpy image array and resize

    Args:
        tensor (torch.Tensor): The input tensor that should be converted
        resize_to (tuple(int, int)): The desired output size of the array

    Returns:
        (np.ndarray): The input tensor converted to a channel last resized array
    '''

    out_array = tensor.detach().cpu().numpy()
    out_array = np.moveaxis(out_array, 0, 2)  # (CHW) -> (HWC)

    if resize_to is not None:
        out_array = cv2.resize(out_array, dsize=resize_to, interpolation=cv2.INTER_CUBIC)

    return (out_array)

def clear_folder(folder):
    for file in os.listdir(folder):
        file_path = os.path.join(folder, file)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))