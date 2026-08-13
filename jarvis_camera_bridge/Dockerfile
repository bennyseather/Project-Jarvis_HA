FROM python:3.12-alpine
ARG BUILD_ARCH
ARG GO2RTC_VERSION=1.9.14
RUN apk add --no-cache ca-certificates curl ffmpeg && \
    case "${BUILD_ARCH}" in \
      amd64) GO_ARCH=amd64 ;; \
      aarch64) GO_ARCH=arm64 ;; \
      *) echo "Unsupported architecture: ${BUILD_ARCH}"; exit 1 ;; \
    esac && \
    curl -fL "https://github.com/AlexxIT/go2rtc/releases/download/v${GO2RTC_VERSION}/go2rtc_linux_${GO_ARCH}" -o /usr/local/bin/go2rtc && \
    chmod 0755 /usr/local/bin/go2rtc
RUN pip install --no-cache-dir aiohttp==3.11.18
WORKDIR /app
COPY app /app
COPY run.sh /run.sh
RUN chmod 0755 /run.sh
CMD ["/run.sh"]
