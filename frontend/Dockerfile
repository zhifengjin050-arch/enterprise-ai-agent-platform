# Build stage — Vite lives in devDependencies, so install the full lockfile.
FROM node:22-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci && npm cache clean --force
COPY . .
RUN npm run build

# Production stage
FROM nginx:1.27-alpine

RUN apk add --no-cache wget

ENV BACKEND_HOST=backend
ENV NGINX_ENVSUBST_FILTER=BACKEND_HOST

COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
