FROM arm64v8/debian:buster

RUN apt-get update && apt-get install -y wget gnupg \
    && rm /etc/apt/sources.list  && rm -rf /var/lib/apt/lists \
    && wget -qO - https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add -

COPY docker/coral-dev-board/multistrap* /etc/apt/sources.list.d/

# The `python3-opencv` package is old and doesn't support gstreamer video writer on Debian. So we need to manually build opencv.
ARG OPENCV_VERSION=4.3.0
RUN apt-get update && apt-get install -y --no-install-recommends \
        cmake \
        curl \
        g++ \
        gcc \
        git \
        gstreamer1.0-plugins-bad \
        gstreamer1.0-plugins-good \
        gstreamer1.0-plugins-ugly \
        gstreamer1.0-vaapi \
        libavcodec-dev \
        libavformat-dev \
        libgstreamer-plugins-base1.0-dev \
        libgstreamer1.0-dev \
        libsm6 \
        libswscale-dev \
        libxext6 \
        libxrender-dev \
        make \
        mesa-va-drivers \
        pkg-config \
        python3-dev \
        python3-numpy \
    && rm -rf /var/lib/apt/lists/* \
    && cd /tmp/ \
    && curl -L https://github.com/opencv/opencv/archive/${OPENCV_VERSION}.tar.gz -o opencv.tar.gz \
    && tar zxvf opencv.tar.gz && rm opencv.tar.gz \
    && cd /tmp/opencv-${OPENCV_VERSION} \
    && mkdir build \
    && cd build \
    && cmake -DBUILD_opencv_python3=yes -DPYTHON_EXECUTABLE=$(which python3) ../ \
    && make -j$(nproc) \
    && make install \
    && cd /tmp \
    && rm -rf opencv-${OPENCV_VERSION} \
    && apt-get purge -y \
        cmake \
        git \
        libgstreamer-plugins-base1.0-dev \
        libgstreamer1.0-dev \
        libxrender-dev \
        python3-dev \
    && apt-get autoremove -y

# https://askubuntu.com/questions/909277/avoiding-user-interaction-with-tzdata-when-installing-certbot-in-a-docker-contai
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        libedgetpu1-std \
        pkg-config \
        python3-dev \
        python3-numpy \
        python3-pillow \
        python3-pip \
        python3-scipy \
        python3-wget \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m pip install --upgrade pip setuptools==41.0.0 && pip install \
        https://dl.google.com/coral/python/tflite_runtime-2.1.0.post1-cp37-cp37m-linux_aarch64.whl \
        aiofiles \
        fastapi \
        uvicorn \
    && apt-get purge -y \
        python3-dev \
    && apt-get autoremove -y

ENV DEV_ALLOW_ALL_ORIGINS=true

# Also if you use opencv: LD_PRELOAD="/usr/lib/aarch64-linux-gnu/libgomp.so.1.0.0"
COPY . /repo
WORKDIR /repo
ENTRYPOINT ["bash", "start_services.bash"]
CMD ["config-coral.ini"]
