"""Sinerji ağırlıkları — tek ayar dosyası.

Şartname 9.3: *"Ağırlıklar tek bir ayar dosyasında toplanır. Motorun içine
dağıtılmaz. Sebep: bu ağırlıklar mutlaka ayarlanacak, her seferinde kod aramak
istemezsin."*

## Ölçek

Sinerji skoru **[0, 1] aralığındadır**. Kalite eşiği (`.env` içinde varsayılan
0.35) bu ölçekte okunur, dolayısıyla ağırlıkları değiştirmek eşiğin anlamını
kaydırmaz.

Skor iki parçadan oluşur:

```
temel  = (arz_talep × w_sd + sektör × w_sektör + şehir × w_şehir) / (w_sd + w_sektör + w_şehir)
skor   = kırp(temel + talep_bonusu − benzerlik_cezası, 0, 1)
```

Arz-talep bileşeni etiket eşleşmesini iki düzeyde okur — tam etiket ve
kategori. Ayrıntı `category_credit` alanının yanında.

Temel kısım ağırlık toplamına bölündüğü için her zaman [0, 1] içinde kalır;
ağırlıkların oranı önemlidir, mutlak büyüklükleri değil. Talep bonusu ve
benzerlik cezası bunun üstüne eklenir.

## Başlangıç değerleri

Şartname Bölüm 12 bu değerleri açık karar olarak işaretliyor: *"Sinerji skoru
bileşenlerinin başlangıç ağırlıkları (test verisiyle ayarlanacak)."*

Buradaki sayılar 9.3'ün sıralamasını izler — arz-talep en ağırlıklı, coğrafya en
hafif — ama gerçek veriyle ayarlanmadan nihai sayılmamalıdır.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SynergyWeights:
    """Sinerji skorunun bileşen ağırlıkları ve biçim parametreleri."""

    # --- Bileşen ağırlıkları (temel kısım, birbirine göre okunur) ---

    # Arz-talep eşleşmesi: 9.3'e göre en ağırlıklı bileşen.
    supply_demand: float = 1.0

    # Sektör ilişkisi. "Aynı sektör = iyi" değil — açıklaması aşağıda.
    sector: float = 0.35

    # Coğrafi yakınlık: "aynı şehir küçük bir artı".
    city: float = 0.10

    # --- Arz-talep biçimi ---

    # Kaç ortak etiketten sonra doyuma ulaşılır. Bunun üstü ek puan getirmez:
    # yirmi ortak etiket, üç ortak etiketten yedi kat daha iyi bir görüşme
    # anlamına gelmiyor.
    supply_demand_saturation: int = 3

    # Çift yönlü eşleşmenin ek değeri. Terim:
    #
    #     arz_talep = min( (ileri+geri)/2 + bonus × min(ileri, geri) , 1 )
    #
    # `min(ileri, geri)` yalnızca iki yön de doluyken sıfırdan farklı olduğu için
    # karşılıklı fayda kendiliğinden öne çıkar (9.3: "tek yönlüden çok daha
    # değerli"). Toplam 1'e **kırpılır, bölünmez**: bölme tek yönlü eşleşmeyi iki
    # kez cezalandırıyordu — hem ortalama hem bölen küçültüyor, mükemmel tek
    # yönlü bir eşleşme bile kalite eşiğinin altında kalıyordu.
    mutual_supply_demand_bonus: float = 0.6

    # --- Kategori düzeyinde kısmi puan (9.3) ---

    # Tam etiket eşleşmesi olmadığında, aynı **kategoride** buluşan ikiliye
    # verilen puanın tam eşleşmeye oranı.
    #
    # Sebep: etiketler ince bölündükçe alıcıyla satıcı aynı kelimeyi seçmiyor.
    # "Backend geliştirme" sunan ile "Web yazılımı" arayan bugün sıfır alıyor,
    # oysa ikisi de "Yazılım ve teknoloji" kategorisinde ve muhtemelen iyi bir
    # görüşme.
    #
    # Terim:
    #
    #     ileri = max( tam_oran , category_credit × kategori_oranı )
    #
    # `max`, toplam değil: tam eşleşme kategoriyi **gölgeler**. Toplasaydık
    # etiketi tutan ikili bir de kategoriden puan alır ve doyum anlamını
    # yitirirdi.
    #
    # 0.0 verilirse davranış kategori öncesiyle birebir aynıdır; bir test bunu
    # kilitliyor.
    #
    # **Üst sınır `1 / supply_demand_saturation`.** Kategori örtüşmesi tek bir
    # tam etiket eşleşmesini geçmemeli — bir tam eşleşme, "aynı iki
    # kategorideyiz"den daha güçlü bir kanıt. Ayrı bir test bu sınırı koruyor.
    category_credit: float = 0.30

    # Kaç ortak kategoriden sonra doyuma ulaşılır. **Bir.**
    #
    # Kişi başı asgari üç etiket (M2) pratikte bir ya da iki kategoriye
    # düşüyor; iki ortak kategori nadir. Doyum 2 olduğunda tek ortak kategori
    # yalnızca yarım puan alıyordu ve kısmi puan etkisiz kalıyordu. Ölçüldü:
    # 120 etiketlik havuzda ortalama masa skoru doyum 2 ile 0.128, doyum 1 ile
    # 0.317 (`docs/kararlar.md`).
    category_saturation: int = 1

    # --- Talep bonusu (temelin üstüne eklenir) ---

    # 9.3: "Karşılıklı talep çok büyük artı." A B'yi istiyor ve B de A'yı
    # istiyorsa bu neredeyse kesin eşleşmedir (M9).
    request_mutual_bonus: float = 0.35

    # "Tek taraflı talep orta artı." Güçlü bir tercih, garanti değil.
    request_one_way_bonus: float = 0.12

    # --- Çeşitlilik cezası (temelden düşülür) ---

    # 9.3: etiketleri neredeyse tıpatıp aynı olan iki kişi birbirine bir şey
    # katmaz. "Küçük bir ceza" — bu yüzden değer düşük tutuldu.
    similarity_penalty: float = 0.10

    # Ceza yalnızca benzerlik bu eşiğin üstündeyken devreye girer ve eşikten
    # 1.0'a doğru doğrusal artar. "Neredeyse tıpatıp aynı" kaydı bu.
    similarity_threshold: float = 0.80

    @property
    def base_weight_total(self) -> float:
        """Temel kısmın normalleştirme böleni."""
        return self.supply_demand + self.sector + self.city


# Motorun her yerinde kullanılan varsayılan. Ayarlamak için `EngineSettings`
# içine farklı bir `SynergyWeights` verilir; kod değiştirmek gerekmez.
DEFAULT_WEIGHTS = SynergyWeights()
