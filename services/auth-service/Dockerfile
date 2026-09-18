FROM node:20-alpine

WORKDIR /app

# Install dependencies first (layer caching)
COPY package.json ./
RUN npm install --omit=dev

COPY src/ ./src/

# Create data directory for SQLite
RUN mkdir -p /app/data

EXPOSE 8086

# Run seed on first start then start the server
CMD ["sh", "-c", "node src/scripts/seed.js && node src/index.js"]
