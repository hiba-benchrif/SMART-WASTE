# Dockerfile frontend — Serveur Nginx pour SmartWaste
# Sert les pages HTML statiques et proxifie les requêtes /api vers le backend
FROM nginx:alpine
COPY . /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
