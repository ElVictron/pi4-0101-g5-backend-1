#!/bin/sh
# Gera a CA local e os certificados do Backend 2 (HTTPS e WSS) e do Backend 1 (HTTPS)
# para o Compose (card #780).
# Uso: sh scripts/gerar-certificados.sh      (grava em ./certs; CERTS_DIR muda a pasta)
# Já existindo, não regera; FORCE=1 apaga e gera de novo.
# A CA e o certificado trazem keyUsage/basicConstraints: o Python 3.13+ (verificação
# estrita do OpenSSL 3.5) recusa uma CA sem keyUsage.
# Só para desenvolvimento e demonstração: a chave fica legível (644) porque o
# contêineres rodam com UIDs próprios (Backend 1: 10001; Backend 2: 10002).
set -eu

PASTA="${CERTS_DIR:-certs}"
DIAS="${DIAS:-825}"

# Emite um certificado de servidor assinado pela CA local: emitir NOME
emitir() {
  nome="$1"
  cat > "$PASTA/$nome.cnf" <<CNF
[req]
distinguished_name = dn
prompt = no
[dn]
CN = $nome
[ext]
subjectAltName = DNS:localhost,DNS:$nome,IP:127.0.0.1,IP:::1
basicConstraints = critical,CA:FALSE
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid
CNF
  openssl req -newkey rsa:2048 -nodes \
    -keyout "$PASTA/$nome-key.pem" -out "$PASTA/$nome.csr" \
    -config "$PASTA/$nome.cnf" 2>/dev/null
  openssl x509 -req -in "$PASTA/$nome.csr" -days "$DIAS" \
    -CA "$PASTA/ca.pem" -CAkey "$PASTA/ca-key.pem" -CAcreateserial \
    -extfile "$PASTA/$nome.cnf" -extensions ext \
    -out "$PASTA/$nome.pem" 2>/dev/null
  rm -f "$PASTA/$nome.csr" "$PASTA/$nome.cnf" "$PASTA/ca.srl"
}

if [ -f "$PASTA/backend2.pem" ] && [ -f "$PASTA/backend1.pem" ] && [ -f "$PASTA/ca.pem" ] \
  && [ "${FORCE:-0}" != "1" ]; then
  echo "Certificados já existem em $PASTA (use FORCE=1 para gerar de novo)."
  exit 0
fi

mkdir -p "$PASTA"

# Certificados antigos só do Backend 2: emite o do Backend 1 com a mesma CA, sem
# trocar a CA (quem já confiou em ca.pem no navegador não precisa importar de novo).
if [ -f "$PASTA/backend2.pem" ] && [ -f "$PASTA/ca.pem" ] && [ -f "$PASTA/ca-key.pem" ] \
  && [ "${FORCE:-0}" != "1" ]; then
  emitir backend1
  chmod 644 "$PASTA"/*.pem
  echo "Certificado do Backend 1 emitido em $PASTA com a CA que já existia."
  exit 0
fi

rm -f "$PASTA"/*.pem "$PASTA"/*.srl "$PASTA"/*.cnf

openssl req -x509 -newkey rsa:2048 -nodes -days "$DIAS" \
  -subj "/CN=PI4 Biblioteca CA local" \
  -addext "basicConstraints=critical,CA:TRUE" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -addext "subjectKeyIdentifier=hash" \
  -keyout "$PASTA/ca-key.pem" -out "$PASTA/ca.pem" 2>/dev/null

emitir backend2
emitir backend1
chmod 644 "$PASTA"/*.pem

echo "Certificados gerados em $PASTA:"
echo "  ca.pem            confie nele no navegador (e nos clientes) para abrir HTTPS e WSS sem aviso"
echo "  backend1.pem      certificado do Backend 1 (nomes: localhost, backend1, 127.0.0.1)"
echo "  backend1-key.pem  chave do Backend 1"
echo "  backend2.pem      certificado do Backend 2 (nomes: localhost, backend2, 127.0.0.1)"
echo "  backend2-key.pem  chave do Backend 2"
