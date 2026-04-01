FROM swaggerapi/swagger-ui:latest AS swagger-ui

FROM nginx:alpine

COPY --from=swagger-ui /usr/share/nginx/html /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY swagger-initializer.js /usr/share/nginx/html/swagger-initializer.js

EXPOSE 8080
