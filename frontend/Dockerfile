FROM node:20-alpine AS build

WORKDIR /app

ARG VITE_API_BASE_URL=/api
ARG VITE_TRANSCRIPTION_ENABLED=false

ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_TRANSCRIPTION_ENABLED=${VITE_TRANSCRIPTION_ENABLED}

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
