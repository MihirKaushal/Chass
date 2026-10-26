
Chess Top Down - v2 chess2
==============================

This dataset was exported via roboflow.ai on May 31, 2022 at 10:13 AM GMT

It includes 327 images.
Chess-pieces are annotated in COCO format.

The following pre-processing was applied to each image:
* Auto-orientation of pixel data (with EXIF-orientation stripping)
* Resize to 416x416 (Stretch)

The following augmentation was applied to create 3 versions of each source image:
* 50% probability of horizontal flip
* Random rotation of between -15 and +15 degrees
* Random brigthness adjustment of between -15 and +15 percent
* Random exposure adjustment of between -25 and +25 percent
* Random Gaussian blur of between 0 and 1.25 pixels

The following transformations were applied to the bounding boxes of each image:
* Salt and pepper noise was applied to 1 percent of pixels


