# syntax=docker/dockerfile:1

FROM eclipse-temurin:21-jdk

# The image version label is added by CI from pack.env (org.opencontainers.image.version).

RUN apt-get update && apt-get install -y curl unzip jq && \
    adduser --uid 99 --gid 100 --home /data --disabled-password minecraft

COPY --chmod=755 launch.sh /launch.sh
COPY --chmod=644 pack.env /pack.env

USER minecraft

VOLUME /data
WORKDIR /data

EXPOSE 25565/tcp

CMD ["/launch.sh"]
