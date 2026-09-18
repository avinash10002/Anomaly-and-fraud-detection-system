FROM node:20-alpine
WORKDIR /app
COPY healthcheck.js .
EXPOSE 8083
ENV SERVICE_PORT=8083
CMD ["node", "healthcheck.js"]
