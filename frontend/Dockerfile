# DocAgent 前端镜像:node 构建 dist → nginx 托管 SPA,并反代 /api /mcp /a2a 到 backend
FROM node:20-alpine AS build
WORKDIR /app

# 先装依赖(利用层缓存)
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
