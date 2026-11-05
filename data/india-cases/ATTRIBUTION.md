# India demo photos: attribution

The photos in `img/` are road photos from the **RDD2022** road damage dataset (India subset), and `selection.json`
holds the dataset's own damage labels for them (class and box, in pixels).

> Arya, D., Maeda, H., Ghosh, S. K., Toshniwal, D., & Sekimoto, Y. (2024). RDD2022: A multi-national image dataset for
> automatic road damage detection. *Geoscience Data Journal*, 11(4).
> Data: https://figshare.com/articles/dataset/RDD2022_-_The_multi-national_Road_Damage_Dataset_released_through_CRDDC_2022/21431547
> (CC BY 4.0 on figshare; the project's GitHub page, https://github.com/sekilab/RoadDamageDetector, states CC BY-SA 4.0).

Faces and number plates in the dataset were blurred by its authors. 200 photos were picked (about half with potholes, the
rest cracks) and are used unmodified.

`scripts/seed_india.py` turns them into DEMO reports. Places and dates are made up, severity and size are worked out from
the labels by simple rules, and no AI model was run. Every such report is stored with `is_demo = 1` and shows the Demo badge.
