import json
import os
import time
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign
from facebook_business.adobjects.adset import AdSet
from facebook_business.adobjects.ad import Ad
from facebook_business.adobjects.adcreative import AdCreative
from facebook_business.adobjects.adimage import AdImage
from facebook_business.adobjects.targeting import Targeting
from facebook_business.adobjects.targetingsearch import TargetingSearch

API_VERSION = "v22.0"

OBJETIVOS = {
    "VENDAS": "SALES",
    "LEADS": "LEADS",
    "TRAFEGO": "TRAFFIC",
    "RECONHECIMENTO": "BRAND_AWARENESS",
    "ENGAGEMENT": "ENGAGEMENT",
    "CATALOGO": "CATALOG_SALES",
}

STATUS_CAMPANHA = {"ATIVO": "ACTIVE", "PAUSADO": "PAUSED"}


class AdsError(Exception):
    pass


class AdManager:
    def __init__(self, access_token, ad_account_id):
        self.access_token = access_token
        self.ad_account_id = ad_account_id
        FacebookAdsApi.init(access_token=access_token)
        self.account = AdAccount(ad_account_id)

    # ── Campanhas ──────────────────────────────────────────────

    def listar_campanhas(self):
        try:
            campanhas = self.account.get_campaigns(
                fields=[
                    "id", "name", "status", "objective",
                    "daily_budget", "lifetime_budget",
                    "created_time", "start_time", "stop_time",
                ]
            )
            return [c for c in campanhas]
        except Exception as e:
            raise AdsError(f"Erro ao listar campanhas: {e}")

    def criar_campanha(self, nome, objetivo, status="PAUSED",
                       daily_budget=None, lifetime_budget=None):
        params = {
            Campaign.Field.name: nome,
            Campaign.Field.objective: OBJETIVOS.get(objetivo.upper(), objetivo),
            Campaign.Field.status: STATUS_CAMPANHA.get(status.upper(), status),
            "special_ad_categories": [],
        }
        if daily_budget:
            params[Campaign.Field.daily_budget] = int(float(daily_budget) * 100)
        if lifetime_budget:
            params[Campaign.Field.lifetime_budget] = int(float(lifetime_budget) * 100)

        try:
            campanha = Campaign(parent_id=self.ad_account_id)
            campanha.update(params)
            campanha.remote_create()
            return campanha
        except Exception as e:
            raise AdsError(f"Erro ao criar campanha: {e}")

    def pausar_campanha(self, campaign_id):
        try:
            campanha = Campaign(campaign_id)
            campanha[Campaign.Field.status] = "PAUSED"
            campanha.remote_update()
            return True
        except Exception as e:
            raise AdsError(f"Erro ao pausar campanha: {e}")

    def ativar_campanha(self, campaign_id):
        try:
            campanha = Campaign(campaign_id)
            campanha[Campaign.Field.status] = "ACTIVE"
            campanha.remote_update()
            return True
        except Exception as e:
            raise AdsError(f"Erro ao ativar campanha: {e}")

    # ── Conjuntos de Anúncios ──────────────────────────────────

    def criar_conjunto(self, nome, campaign_id, daily_budget,
                       targeting_spec, optimization_goal="REACH",
                       billing_event="IMPRESSIONS", start_time=None,
                       end_time=None):
        params = {
            AdSet.Field.name: nome,
            AdSet.Field.campaign_id: campaign_id,
            AdSet.Field.daily_budget: int(float(daily_budget) * 100),
            AdSet.Field.billing_event: billing_event,
            AdSet.Field.optimization_goal: optimization_goal,
            AdSet.Field.status: "PAUSED",
        }
        if targeting_spec:
            params[AdSet.Field.targeting] = targeting_spec
        if start_time:
            params[AdSet.Field.start_time] = start_time
        if end_time:
            params[AdSet.Field.end_time] = end_time

        try:
            adset = AdSet(parent_id=self.ad_account_id)
            adset.update(params)
            adset.remote_create()
            return adset
        except Exception as e:
            raise AdsError(f"Erro ao criar conjunto: {e}")

    # ── Anúncios ───────────────────────────────────────────────

    def criar_anuncio(self, nome, adset_id, creative_id, status="PAUSED"):
        params = {
            Ad.Field.name: nome,
            Ad.Field.adset_id: adset_id,
            Ad.Field.creative: {"creative_id": creative_id},
            Ad.Field.status: STATUS_CAMPANHA.get(status.upper(), status),
        }
        try:
            anuncio = Ad(parent_id=self.ad_account_id)
            anuncio.update(params)
            anuncio.remote_create()
            return anuncio
        except Exception as e:
            raise AdsError(f"Erro ao criar anúncio: {e}")

    # ── Criativos ──────────────────────────────────────────────

    def criar_creative_imagem(self, nome, image_path, link, headline,
                              description, call_to_action="LEARN_MORE"):
        try:
            image = AdImage(parent_id=self.ad_account_id)
            image[AdImage.Field.filename] = image_path
            image.remote_create()
            image_hash = image[AdImage.Field.hash]
        except Exception as e:
            raise AdsError(f"Erro ao fazer upload da imagem: {e}")

        try:
            creative = AdCreative(parent_id=self.ad_account_id)
            creative[AdCreative.Field.name] = nome
            creative[AdCreative.Field.object_story_spec] = {
                "page_id": None,
                "link_data": {
                    "link": link,
                    "message": description,
                    "name": headline,
                    "call_to_action": {"type": call_to_action},
                    "attachment_style": "link",
                },
            }
            creative.remote_create()
            return creative
        except Exception as e:
            raise AdsError(f"Erro ao criar criativo: {e}")

    def criar_creative_simples(self, nome, message, image_hash=None):
        try:
            creative = AdCreative(parent_id=self.ad_account_id)
            creative[AdCreative.Field.name] = nome
            creative[AdCreative.Field.object_story_spec] = {
                "page_id": None,
                "link_data": {
                    "link": "https://www.example.com",
                    "message": message,
                },
            }
            creative.remote_create()
            return creative
        except Exception as e:
            raise AdsError(f"Erro ao criar criativo: {e}")

    # ── Insights ───────────────────────────────────────────────

    def obter_insights(self, level="campaign", date_preset="last_30d"):
        try:
            params = {
                "level": level,
                "date_preset": date_preset,
            }
            fields = [
                "campaign_name", "spend", "impressions", "clicks",
                "ctr", "cpm", "cpc", "reach", "frequency",
                "actions", "cost_per_action_type",
            ]
            insights = self.account.get_insights(
                fields=fields, params=params
            )
            return insights
        except Exception as e:
            raise AdsError(f"Erro ao obter insights: {e}")

    # ── Utilitários ────────────────────────────────────────────

    @staticmethod
    def buscar_interesses(qtdade, query):
        try:
            params = {
                "q": query,
                "type": "adinterest",
            }
            results = TargetingSearch.search(params=params)
            return results[:qtdade]
        except Exception as e:
            raise AdsError(f"Erro ao buscar interesses: {e}")
