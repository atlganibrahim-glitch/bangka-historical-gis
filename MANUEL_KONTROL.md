# Manuel kontrol noktası çalışması — adım adım

Bu, otomatik testlerin yapamadığı ölçüm. Kişisel çalışma notu (repo
dokümantasyonu İngilizce).

---

## Neden bu gerekiyor

Elimizdeki iki otomatik test de sayfanın **çizili içeriğini** modern bir
katmanla karşılaştırıyor, ve ikisi de 1930'lardan bu yana gerçekten değişmiş
olan şeylerle sınırlı:

- **Kıyı testi** (`fit_singles.py`) → 780 m'de tıkanıyor, çünkü kıyı gerçekten
  o kadar oynamış.
- **Yol testi** (`fit_roads.py`) → 176 sayfanın sadece 60'ında net sonuç
  verdi; 71'inde yollar o kadar değişmiş ki hiçbir kayma onları hizalamıyor.

Ayrıca **ikisi de sayfanın ortasını hiç test etmiyor** — sadece kıyıya veya
yola yakın içeriği görüyorlar. 90 yıllık kağıt eşit büzülmez (katlanma, nem,
tarama eğriliği), yani sayfa köşeleri doğru olsa bile ortası kaymış olabilir.
Bunu şu ana kadar hiç ölçmedik.

Manuel kontrol noktası ikisini birden çözüyor: hem doğrulanamayan %60'ı
kapsıyor, hem sayfa içini örnekliyor.

## Ne ölçeceğiz: kayma ve saçılım

Her sayfa için iki ayrı sayı çıkacak, ve **ikisi çok farklı şeyler**:

- **Kayma (shift)** — sayfanın tamamının sabit bir yöne kaymış olması.
  **Düzeltilebilir**, tek satırlık bir ötelemeyle.
- **Saçılım (scatter)** — en iyi kayma uygulandıktan *sonra* geriye kalan
  dağınıklık. **Düzeltilemez** öteleme ile. Sayfa içi bozulma buradan
  görünür.

Bu yüzden sayfa başına **en az 3, tercihen 5-6 nokta** gerekiyor — 1-2 nokta
ile kaymayı saçılımdan ayıramazsınız.

---

## Aşama 0 — Kapsamı gerçekçi tutun

**176 sayfanın hepsini yapmayın.** Önce **10 sayfalık bir pilot** yapın:

- 5 tane **A grade** (`bangka_sheet_quality.csv`'de `positional_grade = A`) —
  bunların doğruluğunu zaten biliyoruz (~30 m), yani yönteminizin doğru
  çalışıp çalışmadığını kontrol eder. Manuel sonuç ~30 m çıkmalı; çok farklı
  çıkarsa nokta seçiminizde sorun var demektir.
- 5 tane **B grade** — asıl merak ettiğimiz, hiç doğrulanamamış grup.

Pilot sonucuna göre karar verirsiniz:
- Saçılım küçükse (< 60 m) → sayfa başına öteleme yeterli, tüm sayfalara
  yaymak anlamlı.
- Saçılım büyükse (> 60 m) → sayfalar içten bozuk, öteleme çözmez, daha
  yüksek dereceli bir dönüşüm gerekir. Bu da bilinmesi gereken bir sonuç.

Sayfa başına ~10 dakika; pilot toplam ~2 saat.

---

## Aşama 1 — QGIS'i hazırlayın

Katman sırası (üstten alta):

1. `qgis/control_points.gpkg` — kontrol noktalarınız (hazır, boş)
2. `qgis/sheet_index_v3.geojson` — hangi sayfadasınız, görmek için
3. `bangka_v3_1.vrt` — tarihi haritalar
4. **Referans katmanı** (aşağıya bakın)

### Referans olarak ne kullanmalı

| kaynak | nasıl eklenir | ne için |
|---|---|---|
| **OSM Standard** | Browser → XYZ Tiles → OpenStreetMap | Yol kavşakları — **en güvenilir**, vektör veriden çizilmiş |
| **Esri World Imagery** | XYZ Tiles → New Connection, URL aşağıda | Nehir, kıyı, arazi detayı |

```
https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}
```

> **Dikkat:** Uydu görüntüsünün kendi konum hatası vardır (yerine göre
> 5-50 m). Ölçtüğümüz hata 30-200 m mertebesinde olduğu için kabul
> edilebilir, ama **yol kavşağı için OSM'i tercih edin** — o vektör veri,
> GPS izlerinden üretilmiş, daha güvenilir.

---

## Aşama 2 — Kontrol noktası katmanını oluşturun

`qgis/control_points.gpkg` hazır — boş, ama şeması kesin tanımlı
(LineString, EPSG:4326). QGIS'e **Layer → Add Layer → Add Vector Layer** ile
ekleyin.

> **Neden GeoPackage, GeoJSON değil:** QGIS'te boş bir GeoJSON'a canlı
> düzenleme yapmak güvenilir değil — geometri tipi dosyada yazılı olmadığı
> için sürücü yanlış tahmin edip *"Could not commit changes … geometry type
> is not compatible"* hatası veriyor ve **çizdiğiniz her şey kaydedilmeden
> reddediliyor**. GeoPackage'da tip şemada saklı, bu sorun oluşmuyor.

Katman **çizgi (LineString)** tipinde ve şu alanları var:

| alan | ne yazılacak |
|---|---|
| `sheet_id` | `34-XXV-e` gibi — hangi paftada çalıştığınız |
| `feature_type` | `road junction`, `river confluence`, `bridge` … |
| `note` | isteğe bağlı |

---

## Aşama 3 — Nokta seçme kuralları

Bu aşama sonucun kalitesini belirliyor, acele etmeyin.

### İyi kontrol noktaları

- **Yol kavşakları** — özellikle iki ana yolun kesiştiği yerler. En iyisi.
- **Nehir birleşme noktaları** — iki kolun birleştiği tam nokta.
- **Köprüler** — yol ve nehrin kesiştiği yer.
- **Belirgin burun/dil şeklinde kıyı çıkıntıları** — sadece kayalık, sert
  zeminli olanlar.

### Kaçınılması gerekenler

- **Düz kıyı şeridi** — 90 yılda oynamış, üstelik boyunca kaydırılabilir.
- **Kumsallar, mangrov kıyıları, haliç ağızları** — en çok değişen yerler.
- **Yerleşim merkezleri** — köy büyümüş, merkezi kaymış olabilir.
- **Tek bir yol boyunca** noktalar — hepsi aynı hizada olursa kaymayı o yön
  boyunca ölçemezsiniz.
- **Maden sahaları çevresi** — Bangka'da kalay madenciliği araziyi
  tamamen değiştirmiş.

### Dağılım kuralı

Noktaları sayfaya **yayın** — dört köşeye ve ortaya birer tane gibi. Hepsi
bir köşede toplanırsa sayfa içi bozulmayı göremezsiniz, ki bu ölçümün asıl
amaçlarından biri.

---

## Aşama 4 — Çizim iş akışı

Her kontrol noktası **iki köşeli bir çizgi**: nerede görünüyor → nerede
olması gerekiyor.

1. `sheet_index_v3` katmanından hangi sayfada olduğunuzu belirleyin
   (Identify aracıyla tıklayın, `sheet_id`'yi not edin).
2. Tarihi haritada bir kavşak bulun, `1:5000` civarına yakınlaşın.
3. `control_points` katmanını seçin → **Toggle Editing** (kalem ikonu).
4. **Add Line Feature** aracını seçin.
5. **İlk tıklama:** tarihi haritadaki kavşağın tam üstüne.
6. Tarihi harita katmanının görünürlüğünü kapatın (kutucuk) — altındaki
   OSM/uydu görünsün.
7. **İkinci tıklama:** aynı kavşağın modern katmandaki yeri.
8. **Sağ tık** → çizgiyi bitirir, alan formu açılır.
9. `sheet_id` ve `feature_type` doldurun → OK.
10. Tarihi haritayı tekrar açın, sonraki noktaya geçin.

> **İpucu:** 6. adımdaki aç/kapa yerine, tarihi harita katmanının
> **Opacity**'sini %50 yapıp iki katmanı üst üste görebilirsiniz. Daha hızlı
> ama iki kavşağı karıştırma riski var — emin değilseniz aç/kapa yapın.

Sayfa başına 5-6 nokta bitince **Toggle Editing**'i kapatıp **kaydedin**.

### Çizim yönü kritik

Çizgi **her zaman** tarihi haritadan modern konuma doğru olmalı. Ters
çizerseniz o noktanın hata vektörü ters işaretli çıkar ve sayfanın ortalamasını
bozar. Katmanı ok işaretli sembolojiyle göstermek bunu gözle kontrol etmenizi
kolaylaştırır (Symbology → Line → Marker line → arrow).

---

## Aşama 5 — Analizi çalıştırın

```bash
python v3/analyse_control_points.py
```

Çıktı sayfa başına: `n` (nokta sayısı), `dE`/`dN` (doğu/kuzey kayması),
`|shift|` (kaymanın büyüklüğü), `scatter` (kalan saçılım).

Başka bir dosya kullandıysanız yolunu verin:

```bash
python v3/analyse_control_points.py qgis/pilot_points.gpkg
```

---

## Aşama 6 — Sonucu yorumlayın

**Önce A grade sayfalara bakın** — kontrol grubunuz onlar:

- `|shift|` ~30-50 m ve `scatter` küçük çıkarsa → yönteminiz çalışıyor,
  B grade sonuçlarına güvenebilirsiniz.
- `|shift|` çok büyük çıkarsa (birkaç yüz metre) → muhtemelen nokta seçimi
  veya çizim yönü hatası var, Aşama 3-4'ü gözden geçirin.

**Sonra B grade sayfalara bakın** — asıl cevap orada:

| gözlem | anlamı | ne yapmalı |
|---|---|---|
| shift büyük, scatter küçük | Sayfa toptan kaymış, içi sağlam | Sayfa başına öteleme uygula — kolay kazanç |
| shift küçük, scatter küçük | Sayfa zaten doğru | Bir şey yapmaya gerek yok |
| scatter büyük | Sayfa içten bozuk | Öteleme çözmez; yüksek dereceli dönüşüm veya o sayfayı düşük güvenle işaretle |

Script zaten sonunda saçılıma bakıp hangi durumda olduğunuzu söylüyor.

---

## Sonrasında

Pilot sonucu netleşince bana söyleyin:

- Saçılım küçükse → `analyse_control_points.py` çıktısındaki sayfa
  bazlı ötelemeleri `v3/grid.py`'ye bağlayan kodu yazarım, GeoTIFF'ler
  yeniden üretilir ve `bangka_sheet_quality.csv` güncellenir.
- Saçılım büyükse → bu, raporlanması gereken bir bulgu; doğruluk beyanını
  ona göre revize ederiz.

Her iki durumda da `ACCURACY_ASSESSMENT.md`'deki "hiç test edilmedi"
maddesi kapanmış olur.
