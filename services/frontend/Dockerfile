FROM node:20-alpine
WORKDIR /app
# Install a minimal HTTP server that replies {"status":"ok"} on /health
RUN npm install -g json-server serve
COPY healthcheck.js .
EXPOSE 3000
CMD ["node", "healthcheck.js"]
