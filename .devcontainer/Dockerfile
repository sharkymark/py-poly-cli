FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    procps \
    htop \
    net-tools \
    wget \
    dnsutils \
    netcat-traditional \
    traceroute \
    iproute2 \
    lsof \
    iputils-ping \
    telnet \
    jq \
    gawk \
    sudo \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Create a non-root user with known UID/GID
ARG USERNAME=coder
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    # Add sudo support
    && apt-get update \
    && apt-get install -y sudo \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

# Set the default user
USER $USERNAME