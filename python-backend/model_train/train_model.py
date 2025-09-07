import numpy as np
import os
import tensorflow as tf
import cv2
import random
import glob
from keras.layers import Conv2D, Dense, Dropout, MaxPooling2D, Flatten
import matplotlib.pyplot as plt
from sklearn.metrics import accuracy_score, confusion_matrix
import seaborn as sns
from tensorflow.keras.utils import image_dataset_from_directory

# --- Step 1: Set Local Paths and Extract Frames ---
# The base directory where the OEP database is located.
# This path is relative to your working directory: C:\Users\aditya\Documents\GitHub\product-prototyping-lab\python-backend
base_dataset_dir = 'model_train/OEP database/'
# The directory where the extracted frames will be stored.
frames_dataset_dir = 'model_train/frames_dataset/'

train_path = os.path.join(frames_dataset_dir, 'train')
test_path = os.path.join(frames_dataset_dir, 'test')

# Create new directory structure for the frames
# This command will create the directories only if they do not exist, preventing errors.
os.makedirs(os.path.join(train_path, 'cheating'), exist_ok=True)
os.makedirs(os.path.join(train_path, 'non-cheating'), exist_ok=True)
os.makedirs(os.path.join(test_path, 'cheating'), exist_ok=True)
os.makedirs(os.path.join(test_path, 'non-cheating'), exist_ok=True)

# Subject classification from the README file
cheating_subjects = [1, 2, 3, 4, 5, 6, 7, 8, 9, 17, 20, 21, 22, 23, 24]
non_cheating_subjects = [10, 11, 12, 13, 14, 15, 16, 18, 19]

def extract_and_save_frames(video_path, output_dir, num_frames=100):
    """Extracts a random sample of frames from a video and saves them."""
    if not os.path.exists(video_path):
        print(f"Video file not found at: {video_path}")
        return

    video = cv2.VideoCapture(video_path)
    total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    
    if total_frames > num_frames:
        frame_indices = random.sample(range(total_frames), num_frames)
    else:
        frame_indices = range(total_frames)

    for i in frame_indices:
        video.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = video.read()
        if ret:
            frame_filename = os.path.join(output_dir, f'frame_{os.path.basename(video_path)}_{i}.jpg')
            cv2.imwrite(frame_filename, frame)
    video.release()

print("Starting frame extraction...")

# Process cheating subjects
for subject_id in cheating_subjects:
    subject_folder = os.path.join(base_dataset_dir, f'subject{subject_id}')
    video_files = glob.glob(os.path.join(subject_folder, '*[1-2].avi'))
    for video_file in video_files:
        if subject_id in [1, 2, 3]:
            extract_and_save_frames(video_file, os.path.join(test_path, 'cheating'))
        else:
            extract_and_save_frames(video_file, os.path.join(train_path, 'cheating'))

# Process non-cheating subjects
for subject_id in non_cheating_subjects:
    subject_folder = os.path.join(base_dataset_dir, f'subject{subject_id}')
    video_files = glob.glob(os.path.join(subject_folder, '*[1-2].avi'))
    for video_file in video_files:
        if subject_id in [10, 11]:
            extract_and_save_frames(video_file, os.path.join(test_path, 'non-cheating'))
        else:
            extract_and_save_frames(video_file, os.path.join(train_path, 'non-cheating'))

print("Frame extraction complete.")

# --- Step 2: Load Data with image_dataset_from_directory ---
print("\nLoading datasets with tf.keras.utils.image_dataset_from_directory...")

training_set = tf.keras.utils.image_dataset_from_directory(
    train_path,
    labels='inferred',
    label_mode='categorical',
    color_mode='grayscale',
    image_size=(48, 48),
    batch_size=16,
    seed=123,
)

test_set = tf.keras.utils.image_dataset_from_directory(
    test_path,
    labels='inferred',
    label_mode='categorical',
    color_mode='grayscale',
    image_size=(48, 48),
    batch_size=16,
    seed=123,
)

# Normalize the data and set up for caching and prefetching
def normalize_img(image, label):
    image = tf.image.convert_image_dtype(image, dtype=tf.float32)
    return image, label

training_set = training_set.map(normalize_img).cache().prefetch(buffer_size=tf.data.AUTOTUNE)
test_set = test_set.map(normalize_img).cache().prefetch(buffer_size=tf.data.AUTOTUNE)

# --- Step 3: Define the CNN Model Architecture ---
model = tf.keras.models.Sequential()
model.add(Conv2D(filters=32, kernel_size=3, strides=1, padding='same', activation='relu', input_shape=[48, 48, 1]))
model.add(MaxPooling2D(2))
model.add(Conv2D(filters=64, kernel_size=3, strides=1, padding='same', activation='relu'))
model.add(MaxPooling2D(2))
model.add(Flatten())
model.add(Dense(1024, activation='relu'))
model.add(Dropout(0.25))
model.add(Dense(2048, activation='relu'))
model.add(Dense(2, activation='sigmoid'))

model.summary()

# --- Step 4: Compile the Model ---
model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])

# --- Step 5: Train the Model ---
history = model.fit(
    x=training_set,
    validation_data=test_set,
    epochs=50
)

# --- Step 6: Evaluate the Model and Visualize Results ---
y_pred_probs = model.predict(test_set)
y_pred = np.argmax(y_pred_probs, axis=1)
y_true = np.concatenate([y for x, y in test_set], axis=0)
y_true_labels = np.argmax(y_true, axis=1)

print('\nEvaluating performance on test set:')
accuracy = accuracy_score(y_true_labels, y_pred)
print(f'Accuracy: {accuracy:.2f}')

cm = confusion_matrix(y_true_labels, y_pred)
sns.heatmap(cm, annot=True, fmt='g', cmap='Blues', xticklabels=test_set.class_names, yticklabels=test_set.class_names)
plt.xlabel('Predicted label')
plt.ylabel('True label')
plt.title('Confusion Matrix')
plt.show()