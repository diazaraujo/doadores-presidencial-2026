# Datos

Esta carpeta no lleva los CSV en el repo. Traen CPF y CNPJ.

Para regenerar la página, descarga el zip del TSE del 17/10/2026 a las 04:05 y deja aquí estos dos archivos, con el nombre nacional `*_BR.csv`:

- `receitas_candidatos_2026_BR.csv`
- `receitas_candidatos_doador_originario_2026_BR.csv`

Zip: https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2026.zip

Dataset: https://dadosabertos.tse.jus.br/dataset/prestacao-de-contas-eleitorais-2026

Después, en la raíz del repo:

```bash
python3 build_doadores.py
```

Eso reescribe `index.html`. El documento se usa solo para armar Cruzados y no sale en la página.
