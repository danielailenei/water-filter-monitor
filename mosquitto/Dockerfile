# Imaginea oficiala + configuratia "coapta" in imagine.
# Pe Fargate nu exista disc local de montat, ca in docker-compose.
#
# Fixata prin DIGEST: Docker Hub nu publica tag-uri pentru fiecare patch 2.1.x,
# iar "2" se muta la fiecare release. Digest-ul (hash-ul continutului) identifica
# exact aceeasi imagine pentru totdeauna -> build reproductibil.
FROM eclipse-mosquitto:2@sha256:38c0da4f2ef84284d47b3b3eeea1cb3bdeabe81ee10caf0cd5c5ff61ee3ea408

COPY config/mosquitto.conf /mosquitto/config/mosquitto.conf
