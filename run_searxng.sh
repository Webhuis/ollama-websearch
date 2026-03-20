docker run -d \
  --name searxng \
  -p 8080:8080 \
  -e BASE_URL=http://localhost:8080 \
  searxng/searxng:latest
