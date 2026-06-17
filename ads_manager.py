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

STATUS = {"ATIVO": "ACTIVE", "PAUSADO": "PAUSED"}

CTA_OPCOES = {
    "SAIBA_MAIS": "LEARN_MORE",
    "COMPRAR": "SHOP_NOW",
    "CADASTRE_SE": "SIGN_UP",
    "CONTATO": "CONTACT_US",
    "BAIXAR": "DOWNLOAD",
    "VER_MAIS": "SEE_MORE",
}


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
            return self.account.get_campaigns(fields=[
                "id", "name", "status", "objective",
                "daily_budget", "lifetime_budget",
                "created_time", "start_time",
            ])
        except Exception as e:
            raise AdsError(f"Erro ao listar campanhas: {e}")

    def criar_campanha(self, nome, objetivo, status="PAUSED",
                       daily_budget=None, lifetime_budget=None):
        params = {
            Campaign.Field.name: nome,
            Campaign.Field.objective: OBJETIVOS.get(objetivo.upper(), objetivo),
            Campaign.Field.status: STATUS.get(status.upper(), status),
            "special_ad_categories": [],
        }
        if daily_budget:
            params[Campaign.Field.daily_budget] = int(float(daily_budget) * 100)
        if lifetime_budget:
            params[Campaign.Field.lifetime_budget] = int(float(lifetime_budget) * 100)
        try:
            c = Campaign(parent_id=self.ad_account_id)
            c.update(params)
            c.remote_create()
            return c
        except Exception as e:
            raise AdsError(f"Erro ao criar campanha: {e}")

    def pausar_campanha(self, campaign_id):
        try:
            c = Campaign(campaign_id)
            c[Campaign.Field.status] = "PAUSED"
            c.remote_update()
        except Exception as e:
            raise AdsError(f"Erro ao pausar campanha: {e}")

    def ativar_campanha(self, campaign_id):
        try:
            c = Campaign(campaign_id)
            c[Campaign.Field.status] = "ACTIVE"
            c.remote_update()
        except Exception as e:
            raise AdsError(f"Erro ao ativar campanha: {e}")

    # ── Conjuntos (Ad Sets) ────────────────────────────────────

    def criar_conjunto(self, nome, campaign_id, daily_budget,
                       targeting_spec, optimization_goal="REACH",
                       billing_event="IMPRESSIONS",
                       start_time=None):
        params = {
            AdSet.Field.name: nome,
            AdSet.Field.campaign_id: campaign_id,
            AdSet.Field.daily_budget: int(float(daily_budget) * 100),
            AdSet.Field.billing_event: billing_event,
            AdSet.Field.optimization_goal: optimization_goal,
            AdSet.Field.status: "PAUSED",
            AdSet.Field.targeting: targeting_spec,
        }
        if start_time:
            params[AdSet.Field.start_time] = start_time
        try:
            a = AdSet(parent_id=self.ad_account_id)
            a.update(params)
            a.remote_create()
            return a
        except Exception as e:
            raise AdsError(f"Erro ao criar conjunto: {e}")

    def listar_conjuntos(self, campaign_id):
        try:
            c = Campaign(campaign_id)
            return c.get_ad_sets(fields=[
                "id", "name", "status", "daily_budget",
                "targeting", "created_time",
            ])
        except Exception as e:
            raise AdsError(f"Erro ao listar conjuntos: {e}")

    # ── Criativos ──────────────────────────────────────────────

    def criar_creative_imagem(self, nome, page_id, image_path,
                              link, headline, description,
                              call_to_action="LEARN_MORE"):
        try:
            image = AdImage(parent_id=self.ad_account_id)
            image[AdImage.Field.filename] = image_path
            image.remote_create()
            image_hash = image[AdImage.Field.hash]
        except Exception as e:
            raise AdsError(f"Erro upload imagem: {e}")

        try:
            creative = AdCreative(parent_id=self.ad_account_id)
            creative[AdCreative.Field.name] = nome
            creative[AdCreative.Field.object_story_spec] = {
                "page_id": page_id,
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

    # ── Anúncios ───────────────────────────────────────────────

    def criar_anuncio(self, nome, adset_id, creative_id, status="PAUSED"):
        params = {
            Ad.Field.name: nome,
            Ad.Field.adset_id: adset_id,
            Ad.Field.creative: {"creative_id": creative_id},
            Ad.Field.status: STATUS.get(status.upper(), status),
        }
        try:
            a = Ad(parent_id=self.ad_account_id)
            a.update(params)
            a.remote_create()
            return a
        except Exception as e:
            raise AdsError(f"Erro ao criar anúncio: {e}")

    def listar_anuncios(self, adset_id):
        try:
            a = AdSet(adset_id)
            return a.get_ads(fields=["id", "name", "status", "creative", "created_time"])
        except Exception as e:
            raise AdsError(f"Erro ao listar anúncios: {e}")

    # ── Função completa: cria campanha + conjunto + anúncio ────

    def criar_campanha_completa(self, dados):
        """
        dados = {
            "campanha": {"nome", "objetivo", "daily_budget"},
            "segmentacao": {"locais", "idade_min", "idade_max", "genero", "interesses"},
            "criativo": {"page_id", "image_path", "link", "headline", "descricao", "cta"},
        }
        """
        camp = self.criar_campanha(
            nome=dados["campanha"]["nome"],
            objetivo=dados["campanha"]["objetivo"],
            daily_budget=dados["campanha"]["daily_budget"],
        )
        camp_id = camp["id"]
        print(f"  Campanha criada: {camp_id}")

        targeting = self._montar_targeting(dados.get("segmentacao", {}))
        adset = self.criar_conjunto(
            nome=f"{dados['campanha']['nome']} - Conjunto",
            campaign_id=camp_id,
            daily_budget=dados["campanha"]["daily_budget"],
            targeting_spec=targeting,
        )
        adset_id = adset["id"]
        print(f"  Conjunto criado: {adset_id}")

        criativo = dados.get("criativo", {})
        if criativo.get("image_path"):
            creative = self.criar_creative_imagem(
                nome=f"{dados['campanha']['nome']} - Criativo",
                page_id=criativo["page_id"],
                image_path=criativo["image_path"],
                link=criativo.get("link", "https://example.com"),
                headline=criativo.get("headline", ""),
                description=criativo.get("descricao", ""),
                call_to_action=CTA_OPCOES.get(
                    criativo.get("cta", "SAIBA_MAIS"), "LEARN_MORE"
                ),
            )
            creative_id = creative["id"]
            print(f"  Criativo criado: {creative_id}")

            anuncio = self.criar_anuncio(
                nome=dados["campanha"]["nome"],
                adset_id=adset_id,
                creative_id=creative_id,
            )
            print(f"  Anúncio criado: {anuncio['id']}")
            return {"campanha": camp_id, "conjunto": adset_id, "anuncio": anuncio["id"]}

        return {"campanha": camp_id, "conjunto": adset_id}

    def _montar_targeting(self, seg):
        t = Targeting()
        locais = seg.get("locais", "").strip()
        if locais:
            geo_locations = {"location_types": ["recent", "home"]}
            ids = []
            for nome in [l.strip() for l in locais.split(",") if l.strip()]:
                try:
                    r = TargetingSearch.search(params={
                        "q": nome, "type": "adgeolocation",
                        "location_types": "['city']",
                    })
                    if r:
                        loc = r[0]
                        ids.append({"key": loc.get("key"),
                                     "name": loc.get("name"),
                                     "type": loc.get("type", "city")})
                except Exception:
                    pass
            if ids:
                geo_locations["cities"] = ids
            t["geo_locations"] = geo_locations

        idade_min = seg.get("idade_min")
        if idade_min:
            t["age_min"] = int(idade_min)
        idade_max = seg.get("idade_max")
        if idade_max:
            t["age_max"] = int(idade_max)

        genero = seg.get("genero", "").upper()
        if genero == "M":
            t["genders"] = [1]
        elif genero == "F":
            t["genders"] = [2]

        interesses = seg.get("interesses", "")
        if interesses:
            interesse_ids = []
            for nome in [i.strip() for i in interesses.split(",") if i.strip()]:
                try:
                    r = TargetingSearch.search(params={
                        "q": nome, "type": "adinterest",
                    })
                    if r:
                        interesse_ids.append({"id": r[0].get("id"),
                                              "name": r[0].get("name")})
                except Exception:
                    pass
            if interesse_ids:
                t["interests"] = interesse_ids

        return t

    # ── Insights ───────────────────────────────────────────────

    def obter_insights(self, level="campaign", date_preset="last_30d"):
        try:
            return self.account.get_insights(fields=[
                "campaign_name", "spend", "impressions", "clicks",
                "ctr", "cpm", "cpc", "reach", "frequency",
                "actions", "cost_per_action_type",
            ], params={"level": level, "date_preset": date_preset})
        except Exception as e:
            raise AdsError(f"Erro ao obter insights: {e}")
