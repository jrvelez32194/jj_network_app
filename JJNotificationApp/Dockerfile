# Stage 1: Build (use Node.js 20 with Debian slim for ARM compatibility)
FROM node:20-slim AS build

WORKDIR /app

# Install build tools (for some npm packages)
RUN apt-get update && apt-get install -y \
    bash git python3 make g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy only package files first
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the source
COPY . .

# Ensure vite is accessible
ENV PATH="/app/node_modules/.bin:$PATH"
RUN chmod +x node_modules/.bin/vite

# Pass API base URL if needed
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Build production assets
RUN npm run build

# Stage 2: Serve
FROM nginx:alpine

# Copy built files
COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom nginx.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
