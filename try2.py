import io
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("TkAgg")



# 2. 用 PIL 打开
img = Image.open('utils/hand.png')
img_resized = img.resize((266, 575), Image.LANCZOS)

# 3. 用 matplotlib 显示
plt.imshow(img_resized)
plt.axis("off")
plt.show()
