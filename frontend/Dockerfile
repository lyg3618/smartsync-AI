FROM node:20-alpine AS build

WORKDIR /app

ARG VITE_API_BASE_URL=/api
ARG VITE_TRANSCRIPTION_ENABLED=false

ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_TRANSCRIPTION_ENABLED=${VITE_TRANSCRIPTION_ENABLED}

# --------------------------
# 关键：强制走你的 Windows 代理 + 国内镜像
# --------------------------
ENV HTTP_PROXY=http://172.16.31.97:8088
ENV HTTPS_PROXY=http://172.16.31.97:8088
RUN npm config set registry https://registry.npmmirror.com
RUN npm config set strict-ssl false

COPY package*.json ./

# 用 install 不要用 ci
RUN npm install

COPY . .
RUN npm run build

FROM nginx    
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80