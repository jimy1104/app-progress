"""Obtención segura de la llave de Azure AI, según la FORMA elegida en .env.

Basado en el Lab 2 (seguridad) del curso 'Azure AI de la Teoría a la Práctica':
en vez de escribir la llave en el código, se guarda en Azure Key Vault y se
recupera con un 'service principal' (TENANT_ID/APP_ID/APP_PASSWORD).

resolver_credencial() devuelve un objeto de credencial listo para el cliente de
Document Intelligence, eligiendo automáticamente:
  A) AzureKeyCredential  si hay AZURE_DI_KEY.
  B) llave sacada de Key Vault -> AzureKeyCredential  si hay KEY_VAULT_NAME.
  C) DefaultAzureCredential (Managed Identity)  si no hay nada de lo anterior.
"""
from __future__ import annotations
import os
import config


def _key_desde_keyvault() -> str:
    from azure.identity import ClientSecretCredential
    from azure.keyvault.secrets import SecretClient
    vault = os.getenv("KEY_VAULT_NAME")
    secret_name = os.getenv("KV_SECRET_NAME", "AI-Services-Key")
    cred = ClientSecretCredential(
        os.getenv("TENANT_ID"), os.getenv("APP_ID"), os.getenv("APP_PASSWORD"))
    client = SecretClient(f"https://{vault}.vault.azure.net/", cred)
    return client.get_secret(secret_name).value


def resolver_credencial():
    """Devuelve (credencial, descripcion) para DocumentIntelligenceClient."""
    from azure.core.credentials import AzureKeyCredential
    # FORMA A
    if config.AZURE_DI_KEY:
        return AzureKeyCredential(config.AZURE_DI_KEY), "llave directa (.env)"
    # FORMA B
    if os.getenv("KEY_VAULT_NAME"):
        return AzureKeyCredential(_key_desde_keyvault()), "llave desde Key Vault"
    # FORMA C
    from azure.identity import DefaultAzureCredential
    return DefaultAzureCredential(), "Managed Identity"
