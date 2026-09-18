FROM node:20-alpine
WORKDIR /app
COPY healthcheck.js .
EXPOSE 8081
ENV SERVICE_PORT=8081
CMD ["node", "healthcheck.js"]
