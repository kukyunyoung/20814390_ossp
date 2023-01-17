import sys, cv2, os
from keras.models import load_model
import numpy as np
import matplotlib.pyplot as plt
import PIL
import matplotlib.image as mpimg

from helper import resize, test
from sklearn.cluster import KMeans
from collections import Counter
from PIL import Image

img_size = 224
base_path = 'samples'
file_list = sorted(os.listdir(base_path))

# this is most important thing
glasses = cv2.imread('images/glasses.png', cv2.IMREAD_UNCHANGED)

print('model load start')

# 저장한 모델을 넣어주는 부분

bbs_model = load_model('models/bbs_1.h5')
lmks_model = load_model('models/lmks_1.h5')

# 두 이미지를 비교하여 보여줄 helper 함수
def show_img_compar(img_1, img_2):
    f, ax = plt.subplots(1,2,figsize=(10,10))
    ax[0].imshow(img_1)
    ax[1].imshow(img_2)
    ax[0].axis('off')
    ax[1].axis('off')
    f.tight_layout()
    plt.show()

print('model load finish')
print('testing start')

# testing
for f in file_list:
    if '.jpg' not in f:
        continue

    print('imread')

    img = cv2.imread(os.path.join(base_path, f))
    ori_img = img.copy()
    result_img = img.copy()

    print('predict bounding box')

    # predict bounding box
    img, ratio, top, left = resize.resize_img(img)

    inputs = (img.astype('float32') / 255).reshape((1, img_size, img_size, 3))
    pred_bb = bbs_model.predict(inputs)[0].reshape((-1, 2))

    # compute bounding box of original image
    ori_bb = ((pred_bb - np.array([left, top])) / ratio).astype(np.int32)

    # compute lazy bounding box for detecting landmarks
    center = np.mean(ori_bb, axis=0)
    face_size = max(np.abs(ori_bb[1] - ori_bb[0]))
    new_bb = np.array([
        center - face_size * 0.6,
        center + face_size * 0.6
    ]).astype(np.int32)
    new_bb = np.clip(new_bb, 0, 99999)

    print('predict landmarks')

    # predict landmarks
    face_img = ori_img[new_bb[0][1]:new_bb[1][1], new_bb[0][0]:new_bb[1][0]]
    face_img, face_ratio, face_top, face_left = resize.resize_img(face_img)

    face_inputs = (face_img.astype('float32') / 255).reshape((1, img_size, img_size, 3))

    pred_lmks = lmks_model.predict(face_inputs)[0].reshape((-1, 2))

    # compute landmark of original image
    new_lmks = ((pred_lmks - np.array([face_left, face_top])) / face_ratio).astype(np.int32)
    ori_lmks = new_lmks + new_bb[0]

    # visualize
    cv2.rectangle(ori_img, pt1=tuple(ori_bb[0]), pt2=tuple(ori_bb[1]), color=(255, 255, 255), thickness=2)

    for i, l in enumerate(ori_lmks):
        cv2.putText(ori_img, str(i), tuple(l), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.circle(ori_img, center=tuple(l), radius=1, color=(255, 255, 255), thickness=2)

    print('wearing glasses')

    # wearing glasses
    glasses_center = np.mean([ori_lmks[0], ori_lmks[1]], axis=0)
    glasses_size = np.linalg.norm(ori_lmks[0] - ori_lmks[1]) * 2

    angle = -test.angle_between(ori_lmks[0], ori_lmks[1])
    M = cv2.getRotationMatrix2D((glasses.shape[1] / 2, glasses.shape[0] / 2), angle, 1)
    rotated_glasses = cv2.warpAffine(glasses, M, (glasses.shape[1], glasses.shape[0]))

    try:
        result_img = test.overlay_transparent(result_img, rotated_glasses, glasses_center[0], glasses_center[1],
                                         overlay_size=(
                                         int(glasses_size), int(glasses.shape[0] * glasses_size / glasses.shape[1])))
    except:
        print('failed overlay image')

    cv2.imshow('img', ori_img)
    cv2.imshow('result', result_img)
    filename, ext = os.path.splitext(f)
    cv2.imwrite('result/%s_lmks%s' % (filename, ext), ori_img)
    cv2.imwrite('result/%s_result%s' % (filename, ext), result_img)
    
    #####################################
    # 고양이의 눈동자 부분을 잘라서 활용해줄 수 있게 작업해주는 부분
    #crop_img = ori_img[y:y+h , x:x+w] 포맷
    lefteye_crop_img = ori_img[ori_lmks[0][1]-20:ori_lmks[0][1]+40, ori_lmks[0][0]-20:ori_lmks[0][0]+20] # 왼쪽눈 크롭
    righteye_crop_img = ori_img[ori_lmks[1][1]-20:ori_lmks[1][1]+40, ori_lmks[1][0]-20:ori_lmks[1][0]+30] # 오른쪽눈 크롭

    # 고양이 사진을 가져와서 랜드마크점을 이용하여 눈주위 식별 및 색판별
    lefteye_img = lefteye_crop_img.copy() # 원래이미지 가져오기
    lefteye_img = cv2.cvtColor(lefteye_img, cv2.COLOR_BGR2RGB) # bgr 에서 rgb로 바꿔줌
    dim = (500,300)
    lefteye_img = cv2.resize(lefteye_img, dim, interpolation=cv2.INTER_AREA)

    clt = KMeans(n_clusters=5) # n_cluster 조정해서 추출할 색상군의 수를 정할 수 있음 (너무많은 색상군이 검출되면 응용할 것)
    clt.fit(lefteye_img.reshape(-1,3))
    print("clt.labels_ \n")
    clt.labels_
    print("clt.cluster_centers_ \n")
    clt.cluster_centers_

    righteye_img = righteye_crop_img.copy() # 원래이미지 가져오기
    righteye_img = cv2.cvtColor(righteye_img, cv2.COLOR_BGR2RGB) # bgr 에서 rgb로 바꿔줌
    dim = (500,300)
    righteye_img = cv2.resize(righteye_img, dim, interpolation=cv2.INTER_AREA)

    clt = KMeans(n_clusters=5) # n_cluster 조정해서 추출할 색상군의 수를 정할 수 있음 (너무많은 색상군이 검출되면 응용할 것)
    clt.fit(righteye_img.reshape(-1,3))
    print("clt.labels_ \n")
    clt.labels_
    print("clt.cluster_centers_ \n")
    clt.cluster_centers_

    # 팔레트를 보여주는 함수 (구성하는 색 뿐만 아니라 구성하는 색의 비율까지 보여줌)
    def palette_perc(k_cluster):
        width=300
        palette = np.zeros((50,width, 3), np.uint8)

        n_pixels = len(k_cluster.labels_)
        counter = Counter(k_cluster.labels_)
        perc = {}
        for i in counter:
            perc[i] = np.round(counter[i]/n_pixels, 2)
        perc = dict(sorted(perc.items()))

        print(perc)
        print(k_cluster.cluster_centers_)

        step = 0

        for idx, centers in enumerate(k_cluster.cluster_centers_):
            palette[:,step:int(step+perc[idx]*width+1),:] = centers
            step += int(perc[idx]*width+1)
        
        return palette
    
    clt_left = clt.fit(lefteye_img.reshape(-1,3))
    #show_img_compar(lefteye_img, palette_perc(clt_left))
    clt_right = clt.fit(righteye_img.reshape(-1,3))
    #show_img_compar(righteye_img, palette_perc(clt_right))

    palette_left = palette_perc(clt_left)
    palette_right = palette_perc(clt_right)

    cv2.imshow('lefteye', cv2.cvtColor(lefteye_img, cv2.COLOR_BGR2RGB))
    cv2.imshow('lefteye palette', cv2.cvtColor(righteye_img, cv2.COLOR_BGR2RGB))
    cv2.imshow('righteye', cv2.cvtColor(palette_left, cv2.COLOR_BGR2RGB))
    cv2.imshow('righteye palette', cv2.cvtColor(palette_right, cv2.COLOR_BGR2RGB))
    ######################################

    if cv2.waitKey(0) == ord('q'):
        break

print('testing finish')