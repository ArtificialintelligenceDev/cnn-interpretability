"""
Created on Thu Oct 26 11:23:47 2017

@author: Utku Ozbulak - github.com/utkuozbulak
"""
import torch
from torch.nn import ReLU

from misc_functions import (get_params,
                            convert_to_grayscale,
                            save_gradient_images,
                            get_positive_negative_saliency)


class GuidedBackprop():
    """
       Produces gradients generated with guided back propagation from the given image
    """
    def __init__(self, model, processed_im, target_class):
        self.model = model
        self.input_image = processed_im
        self.target_class = target_class
        self.gradients = None

        self.hook_handles = []
        # Put model in evaluation mode
        self.model.eval()
        self.update_relus()
        self.hook_layers()

    def hook_layers(self):
        def hook_function(module, grad_in, grad_out):
            self.gradients = grad_in[0]

        # Register hook to the first layer
        first_layer = list(self.model.features._modules.items())[0][1]
        first_layer.register_backward_hook(hook_function)

    def update_relus(self):
        """
            Updates relu activation functions so that it only returns positive gradients
        """
        def relu_hook_function(module, grad_in, grad_out):
            """
            If there is a negative gradient, changes it to zero
            """
            if isinstance(module, ReLU):
                #print 'in:'
                #print grad_in
                #print 'out'
                #print grad_out
                #print '-'*80
                # Vanilla Backprop: Gradient is 0 where forward is negative. Do nothing because this is already done by the ReLU module.
                #return
                # Deconvolution: Gradient is 0 where gradient is negative. Clamp `grad_out` to 0.
                #return (torch.clamp(grad_out[0], min=0.0),)
                # Guided Backprop: Gradient is 0 where forward or gradient is negative. Clamp `grad_in` to 0.
                return (torch.clamp(grad_in[0], min=0.0),)

        # Loop through layers, hook up ReLUs with relu_hook_function
        for pos, module in self.model.features._modules.items():
            if isinstance(module, ReLU):
                hook_handle = module.register_backward_hook(relu_hook_function)
                self.hook_handles.append(hook_handle)


    def unhook(self):
        for hook_handle in self.hook_handles:
            hook_handle.remove()
            del hook_handle


    def generate_gradients(self):
        # Forward pass
        model_output = self.model(self.input_image)
        # Zero gradients
        self.model.zero_grad()
        # Target for backprop
        one_hot_output = torch.FloatTensor(1, model_output.size()[-1]).zero_()
        one_hot_output[0][self.target_class] = 1
        # Backward pass
        model_output.backward(gradient=one_hot_output)
        # Convert Pytorch variable to numpy array
        # [0] to get rid of the first channel (1,3,224,224)
        gradients_as_arr = self.gradients.data.numpy()[0]
        return gradients_as_arr






if __name__ == '__main__':
    target_example = 0  # Snake
    (original_image, prep_img, target_class, file_name_to_export, pretrained_model) =\
        get_params(target_example)

    # Guided backprop
    GBP = GuidedBackprop(pretrained_model, prep_img, target_class)
    # Get gradients
    guided_grads = GBP.generate_gradients()
    # Save colored gradients
    save_gradient_images(guided_grads, file_name_to_export + '_Guided_BP_color')
    # Convert to grayscale
    grayscale_guided_grads = convert_to_grayscale(guided_grads)
    # Save grayscale gradients
    save_gradient_images(grayscale_guided_grads, file_name_to_export + '_Guided_BP_gray')
    # Positive and negative saliency maps
    pos_sal, neg_sal = get_positive_negative_saliency(guided_grads)
    save_gradient_images(pos_sal, file_name_to_export + '_pos_sal')
    save_gradient_images(neg_sal, file_name_to_export + '_neg_sal')
    print('Guided backprop completed')