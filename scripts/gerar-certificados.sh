#!/bin/sh
# Gera a CA local e o certificado do Backend 2 (HTTPS e WSS) para o Compose (card #780).
# Uso: sh scripts/gerar-certificados.sh      (grava em ./certs; CERTS_DIR muda a pasta)
# Já existindo, não regera; FORCE=1 apaga e gera de novo.
# A CA e o certificado trazem keyUsage/basicConstraints: o Python 3.13+ (verificação
# estrita do OpenSSL 3.5) recusa uma CA sem keyUsage.
# Só para desenvolvimento e demonstração: a chave fica legível (644) porque o
# contêiner do Backend 2 roda com o UID 10002.
set -eu

PASTA="${CERTS_DIR:-certs}"
DIAS="${DIAS:-825}"

if [ -f "$PASTA/backend2.pem" ] && [ -f "$PASTA/ca.pem" ] && [ "${FORCE:-0}" != "1" ]; then
  echo "Certificados já existem em $PASTA (use FORCE=1 para gerar de novo)."
  exit 0
fi

mkdir -p "$PASTA"
rm -f "$PASTA"/*.pem "$PASTA"/*.srl "$PASTA"/*.cnf

openssl req -x509 -newkey rsa:2048 -nodes -days "$DIAS" \
  -subj "/CN=PI4 Biblioteca CA local" \
  -addext "basicConstraints=critical,CA:TRUE" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -addext "subjectKeyIdentifier=hash" \
  -keyout "$PASTA/ca-key.pem" -out "$PASTA/ca.pem" 2>/dev/null

cat > "$PASTA/backend2.cnf" <<CNF
[req]
distinguished_name = dn
prompt = no
[dn]
CN = backend2
[ext]
subjectAltName = DNS:localhost,DNS:backend2,IP:127.0.0.1,IP:::1
basicConstraints = critical,CA:FALSE
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid
CNF

openssl req -newkey rsa:2048 -nodes \
  -keyout "$PASTA/backend2-key.pem" -out "$PASTA/backend2.csr" \
  -config "$PASTA/backend2.cnf" 2>/dev/null

openssl x509 -req -in "$PASTA/backend2.csr" -days "$DIAS" \
  -CA "$PASTA/ca.pem" -CAkey "$PASTA/ca-key.pem" -CAcreateserial \
  -extfile "$PASTA/backend2.cnf" -extensions ext \
  -out "$PASTA/backend2.pem" 2>/dev/null

rm -f "$PASTA/backend2.csr" "$PASTA/backend2.cnf" "$PASTA/ca.srl"
chmod 644 "$PASTA"/*.pem

echo "Certificados gerados em $PASTA:"
echo "  ca.pem            confie nele no navegador (e nos clientes) para abrir o WSS sem aviso"
echo "  backend2.pem      certificado do Backend 2 (nomes: localhost, backend2, 127.0.0.1)"
echo "  backend2-key.pem  chave do Backend 2"
