# 📊 ML Dashboard — Guia de Configuração

## Pré-requisitos
- Python 3.10+ instalado (https://python.org)
- Conta no Mercado Livre Developers

---

## 1. Criar App no Mercado Livre Developers

1. Acesse https://developers.mercadolivre.com.br
2. Faça login com sua conta do Mercado Livre
3. Clique em **"Criar aplicativo"**
4. Preencha:
   - **Nome:** ML Dashboard (ou qualquer nome)
   - **URL de redirect:** `http://localhost:5000/auth/callback`
   - **Escopo:** `read`, `orders`, `shipping`
5. Salve e copie o **Client ID** e **Client Secret**

---

## 2. Configurar credenciais

Abra o arquivo `backend/app.py` e substitua nas linhas iniciais:

```python
CLIENT_ID     = "SEU_CLIENT_ID"      # ← cole aqui
CLIENT_SECRET = "SEU_CLIENT_SECRET"  # ← cole aqui
```

---

## 3. Instalar e rodar

### Windows
Dê duplo clique em **INICIAR.bat**

### Mac/Linux
```bash
cd backend
pip install -r requirements.txt
python app.py
```

Depois abra: http://localhost:5000

---

## 4. Usar o Dashboard

1. Clique em **"Entrar com Mercado Livre"**
2. Autorize o app (só precisa fazer isso uma vez)
3. Selecione o período desejado
4. Clique em **Buscar**
5. Para exportar, clique em **📥 Exportar Excel**

---

## Estrutura de pastas

```
ml-dashboard/
├── INICIAR.bat          ← clique aqui para abrir (Windows)
├── README.md
├── backend/
│   ├── app.py           ← servidor Python
│   ├── requirements.txt
│   └── tokens.json      ← salvo automaticamente após login
└── frontend/
    └── index.html       ← dashboard visual
```

---

## Dúvidas comuns

**"Não consigo fazer login"**
→ Confirme que a URL de redirect no ML Developers é exatamente `http://localhost:5000/auth/callback`

**"Pedidos não aparecem"**
→ Verifique se o período selecionado tem vendas. A API retorna no máximo 50 pedidos por vez.

**"Frete aparece como R$ 0,00"**
→ Alguns fretes são subsidiados pelo ML e têm custo 0 para o vendedor.
