#!/usr/bin/env bash
# Script para configurar permissões de acesso ao /dev/uinput sem precisar rodar como root toda vez.

set -e

echo "Configurando permissão permanente para /dev/uinput..."

# Cria regra udev
RULE_FILE="/etc/udev/rules.d/99-uinput.rules"
echo 'KERNEL=="uinput", MODE="0660", GROUP="input"' | sudo tee "$RULE_FILE" > /dev/null
echo "✓ Regra udev criada em $RULE_FILE"

# Adiciona o usuário atual ao grupo input
CURRENT_USER="${SUDO_USER:-$USER}"
sudo usermod -aG input "$CURRENT_USER"
echo "✓ Usuário '$CURRENT_USER' adicionado ao grupo 'input'"

# Recarrega regras udev
sudo udevadm control --reload-rules
sudo udevadm trigger

# Concede permissão de leitura/escrita na sessão atual para poder testar de imediato sem deslogar
sudo chmod 666 /dev/uinput
echo "✓ Permissão imediata (666) aplicada ao /dev/uinput"

echo ""
echo "Concluído com sucesso!"
echo "Nota: Para a permissão permanente ter efeito em novos terminais sem sudo, faça logout e login novamente para atualizar os grupos do usuário."
