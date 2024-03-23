import sys
from os import path

sys.path.insert(0, path.dirname(__file__))
from folder_paths import get_save_image_path, get_output_directory
from PIL import Image
import numpy as np

class TextureViewer:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {

            },
            "optional": {
                "color_map": ("IMAGE",),
                "displacement_map": ("IMAGE",),
                "normal_map": ("IMAGE",),
                "ao_map": ("IMAGE",),
                "metalness_map": ("IMAGE",),
                "roughness_map": ("IMAGE",),
                "alpha_map": ("IMAGE",),
            },
        }

    def __init__(self):
        self.saved_color = []
        self.saved_displacement = []
        self.saved_normal = []
        self.saved_ao = []
        self.saved_metalness = []
        self.saved_roughness = []
        self.saved_alpha = []
        self.full_output_folder, self.filename, self.counter, self.subfolder, self.filename_prefix = get_save_image_path("imagesave", get_output_directory())


    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = "process_images"
    CATEGORY = "TextureViewer"
    def process_images(self, color_map=None, displacement_map=None, normal_map=None, ao_map=None, metalness_map=None, roughness_map=None, alpha_map=None):
        self.saved_color.clear()
        self.saved_displacement.clear()
        self.saved_normal.clear()
        self.saved_ao.clear()
        self.saved_metalness.clear()
        self.saved_roughness.clear()
        self.saved_alpha.clear()

        if color_map is not None:
            color_map = color_map[0].detach().cpu().numpy()
            color_map = Image.fromarray(np.clip(255. * color_map, 0, 255).astype(np.uint8)).convert('RGB')

        if displacement_map is not None:
            displacement_map = displacement_map[0].detach().cpu().numpy()
            displacement_map = Image.fromarray(np.clip(255. * displacement_map, 0, 255).astype(np.uint8))

        if normal_map is not None:
            normal_map = normal_map[0].detach().cpu().numpy()
            normal_map = Image.fromarray(np.clip(255. * normal_map, 0, 255).astype(np.uint8))

        if ao_map is not None:
            ao_map = ao_map[0].detach().cpu().numpy()
            ao_map = Image.fromarray(np.clip(255. * ao_map, 0, 255).astype(np.uint8))

        if metalness_map is not None:
            metalness_map = metalness_map[0].detach().cpu().numpy()
            metalness_map = Image.fromarray(np.clip(255. * metalness_map, 0, 255).astype(np.uint8))

        if roughness_map is not None:
            roughness_map = roughness_map[0].detach().cpu().numpy()
            roughness_map = Image.fromarray(np.clip(255. * roughness_map, 0, 255).astype(np.uint8))

        if alpha_map is not None:
            alpha_map = alpha_map[0].detach().cpu().numpy()
            alpha_map = Image.fromarray(np.clip(255. * alpha_map, 0, 255).astype(np.uint8))
        print(normal_map)
        return self.display([color_map], [displacement_map], [normal_map], [ao_map], [metalness_map], [roughness_map], [alpha_map])

    def save_and_append(self, image_map, image_type):
        saved_images = []
        if image_map is not None:
            for (batch_number, single_image) in enumerate(image_map):
                filename_with_batch_num = self.filename.replace("%batch_num%", str(batch_number))
                image_file = f"{filename_with_batch_num}_{self.counter:05}_{image_type}.png"
                single_image.save(path.join(self.full_output_folder, image_file))

                saved_images.append({
                    "filename": image_file,
                    "subfolder": self.subfolder,
                    "type": "output"
                })
            return saved_images

    def display(self, color_map=None, displacement_map=None, normal_map=None, ao_map=None, metalness_map=None, roughness_map=None, alpha_map=None):
        map_types = {
            'color': color_map,
            'displacement': displacement_map,
            'normal': normal_map,
            'ao': ao_map,
            'metalness': metalness_map,
            'roughness': roughness_map,
            'alpha': alpha_map
        }

        saved_maps = {
            'color': self.saved_color,
            'displacement': self.saved_displacement,
            'normal': self.saved_normal,
            'ao': self.saved_ao,
            'metalness': self.saved_metalness,
            'roughness': self.saved_roughness,
            'alpha': self.saved_alpha
        }

        for map_type, maps in map_types.items():
            if maps and maps[0] is not None:
                saved_maps[map_type] = self.save_and_append(maps, map_type)

        self.counter += 1

        return {"ui": saved_maps}

    
NODE_CLASS_MAPPINGS = {
    "TextureViewer": TextureViewer,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TextureViewer": "TextureViewer",
}

WEB_DIRECTORY = "./web"

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']
