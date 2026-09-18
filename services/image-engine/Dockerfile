FROM node:20-alpine
WORKDIR /app
COPY healthcheck.js .
EXPOSE 8082
ENV SERVICE_PORT=8082
CMD ["node", "healthcheck.js"]
