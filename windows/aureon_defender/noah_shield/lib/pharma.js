// Pharma: who is behind a medicine, vitamin or remedy, layer by layer, and
// what the herbal world offers in its place.
//
// The surface is a brand on a box (Tylenol, Centrum, Nature Made). Under it
// sit layers: the company that owns the brand, the company that owns that
// one, and at the bottom, often, a pharmaceutical manufacturer or a company
// that was carved out of one. The shield follows the chain and, when it
// ends at pharma, says so plainly and offers herbal alternatives sold by
// companies with no such parent, each with a link to the product and a link
// to check the ownership claim.
//
// Nothing here is medical advice. The herbal alternatives are what herbal
// companies sell for the same purpose; whether any of it suits a person is
// their call and their doctor's. The ownership facts are public record and
// each has a link to verify it.
"use strict";
(() => {

const Shield = (globalThis.Shield = globalThis.Shield || {});

// ---- the companies -------------------------------------------------------------------
// kind: pharma (makes prescription or OTC drugs), consumer-health (a
// consumer-health company carved out of or owned by pharma), conglomerate
// (consumer goods group that owns the brand; not a drug maker), equity
// (private-equity owner), retailer, independent.
const COMPANIES = {
  jnj: { name: "Johnson & Johnson", kind: "pharma", country: "US", verify: "https://en.wikipedia.org/wiki/Johnson_%26_Johnson" },
  kenvue: { name: "Kenvue", kind: "consumer-health", parent: "jnj", lineage: "spun out of Johnson & Johnson in 2023; it is J&J's former consumer-health division", country: "US", verify: "https://en.wikipedia.org/wiki/Kenvue" },
  gsk: { name: "GSK (GlaxoSmithKline)", kind: "pharma", country: "GB", verify: "https://en.wikipedia.org/wiki/GSK_plc" },
  pfizer: { name: "Pfizer", kind: "pharma", country: "US", verify: "https://en.wikipedia.org/wiki/Pfizer" },
  haleon: { name: "Haleon", kind: "consumer-health", parent: "gsk", lineage: "spun out of GSK in 2022 from the GSK–Pfizer consumer-health joint venture", country: "GB", verify: "https://en.wikipedia.org/wiki/Haleon" },
  bayer: { name: "Bayer", kind: "pharma", country: "DE", verify: "https://en.wikipedia.org/wiki/Bayer" },
  sanofi: { name: "Sanofi", kind: "pharma", country: "FR", verify: "https://en.wikipedia.org/wiki/Sanofi" },
  opella: { name: "Opella", kind: "consumer-health", parent: "sanofi", lineage: "Sanofi's consumer-health business, carved out in 2024 (Sanofi kept a large stake; CD&R bought the majority)", country: "FR", verify: "https://en.wikipedia.org/wiki/Opella" },
  reckitt: { name: "Reckitt", kind: "pharma", lineage: "a consumer-goods group that makes over-the-counter medicines (Mucinex, Nurofen, Strepsils, Gaviscon)", country: "GB", verify: "https://en.wikipedia.org/wiki/Reckitt" },
  pg: { name: "Procter & Gamble", kind: "pharma", lineage: "a consumer-goods group whose health division makes over-the-counter medicines (Vicks, Pepto-Bismol, Prilosec OTC)", country: "US", verify: "https://en.wikipedia.org/wiki/Procter_%26_Gamble" },
  perrigo: { name: "Perrigo", kind: "pharma", lineage: "the largest maker of store-brand over-the-counter medicines", country: "IE", verify: "https://en.wikipedia.org/wiki/Perrigo" },
  teva: { name: "Teva Pharmaceutical Industries", kind: "pharma", country: "IL", verify: "https://en.wikipedia.org/wiki/Teva_Pharmaceutical_Industries" },
  novartis: { name: "Novartis", kind: "pharma", country: "CH", verify: "https://en.wikipedia.org/wiki/Novartis" },
  sandoz: { name: "Sandoz", kind: "pharma", parent: "novartis", lineage: "spun out of Novartis in 2023", country: "CH", verify: "https://en.wikipedia.org/wiki/Sandoz" },
  abbvie: { name: "AbbVie", kind: "pharma", country: "US", verify: "https://en.wikipedia.org/wiki/AbbVie" },
  allergan: { name: "Allergan", kind: "pharma", parent: "abbvie", lineage: "bought by AbbVie in 2020", country: "IE", verify: "https://en.wikipedia.org/wiki/Allergan" },
  abbott: { name: "Abbott Laboratories", kind: "pharma", country: "US", verify: "https://en.wikipedia.org/wiki/Abbott_Laboratories" },
  otsuka: { name: "Otsuka Pharmaceutical", kind: "pharma", country: "JP", verify: "https://en.wikipedia.org/wiki/Otsuka_Pharmaceutical" },
  pharmavite: { name: "Pharmavite", kind: "consumer-health", parent: "otsuka", lineage: "owned by Otsuka Pharmaceutical since 1989", country: "US", verify: "https://en.wikipedia.org/wiki/Pharmavite" },
  viatris: { name: "Viatris (Mylan and Upjohn)", kind: "pharma", country: "US", verify: "https://en.wikipedia.org/wiki/Viatris" },
  bausch: { name: "Bausch Health", kind: "pharma", country: "CA", verify: "https://en.wikipedia.org/wiki/Bausch_Health" },
  bauschlomb: { name: "Bausch + Lomb", kind: "pharma", parent: "bausch", lineage: "majority-owned by Bausch Health", country: "CA", verify: "https://en.wikipedia.org/wiki/Bausch_%26_Lomb" },
  alcon: { name: "Alcon", kind: "pharma", lineage: "spun out of Novartis in 2019", country: "CH", verify: "https://en.wikipedia.org/wiki/Alcon" },
  prestige: { name: "Prestige Consumer Healthcare", kind: "pharma", lineage: "an over-the-counter medicine company (Dramamine, Monistat, Clear Eyes)", country: "US", verify: "https://en.wikipedia.org/wiki/Prestige_Consumer_Healthcare" },
  churchdwight: { name: "Church & Dwight", kind: "pharma", lineage: "a consumer-goods group that makes over-the-counter medicines (Zicam, Orajel) and gummy vitamins (Vitafusion, L'il Critters)", country: "US", verify: "https://en.wikipedia.org/wiki/Church_%26_Dwight" },
  schwabe: { name: "Dr. Willmar Schwabe Group", kind: "pharma", lineage: "a German phytopharmaceutical (plant-drug) manufacturer", country: "DE", verify: "https://en.wikipedia.org/wiki/Schwabe_Pharmaceuticals" },
  biocodex: { name: "Biocodex", kind: "pharma", country: "FR", verify: "https://en.wikipedia.org/wiki/Biocodex" },
  boehringer: { name: "Boehringer Ingelheim", kind: "pharma", country: "DE", verify: "https://en.wikipedia.org/wiki/Boehringer_Ingelheim" },
  takeda: { name: "Takeda", kind: "pharma", country: "JP", verify: "https://en.wikipedia.org/wiki/Takeda_Pharmaceutical_Company" },
  daiichi: { name: "Daiichi Sankyo", kind: "pharma", country: "JP", verify: "https://en.wikipedia.org/wiki/Daiichi_Sankyo" },
  taisho: { name: "Taisho Pharmaceutical", kind: "pharma", country: "JP", verify: "https://en.wikipedia.org/wiki/Taisho_Pharmaceutical" },
  kowa: { name: "Kowa", kind: "pharma", country: "JP", verify: "https://en.wikipedia.org/wiki/Kowa_Company" },
  rohto: { name: "Rohto Pharmaceutical", kind: "pharma", country: "JP", verify: "https://en.wikipedia.org/wiki/Rohto_Pharmaceutical" },
  hisamitsu: { name: "Hisamitsu Pharmaceutical", kind: "pharma", country: "JP", verify: "https://en.wikipedia.org/wiki/Hisamitsu_Pharmaceutical" },
  sunpharma: { name: "Sun Pharmaceutical", kind: "pharma", country: "IN", verify: "https://en.wikipedia.org/wiki/Sun_Pharmaceutical" },
  cipla: { name: "Cipla", kind: "pharma", country: "IN", verify: "https://en.wikipedia.org/wiki/Cipla" },
  drreddys: { name: "Dr. Reddy's Laboratories", kind: "pharma", country: "IN", verify: "https://en.wikipedia.org/wiki/Dr._Reddy%27s_Laboratories" },
  lupin: { name: "Lupin", kind: "pharma", country: "IN", verify: "https://en.wikipedia.org/wiki/Lupin_Limited" },
  zydus: { name: "Zydus Lifesciences", kind: "pharma", country: "IN", verify: "https://en.wikipedia.org/wiki/Zydus_Lifesciences" },
  glenmark: { name: "Glenmark Pharmaceuticals", kind: "pharma", country: "IN", verify: "https://en.wikipedia.org/wiki/Glenmark_Pharmaceuticals" },
  dabur: { name: "Dabur", kind: "conglomerate", lineage: "an Ayurvedic consumer-goods group; it is not a pharmaceutical drug maker", country: "IN", verify: "https://en.wikipedia.org/wiki/Dabur" },
  himalaya: { name: "Himalaya Wellness", kind: "independent", lineage: "a privately held herbal company", country: "IN", verify: "https://en.wikipedia.org/wiki/Himalaya_Wellness_Company" },
  hikma: { name: "Hikma Pharmaceuticals", kind: "pharma", country: "GB", verify: "https://en.wikipedia.org/wiki/Hikma_Pharmaceuticals" },
  stada: { name: "STADA Arzneimittel", kind: "pharma", country: "DE", verify: "https://en.wikipedia.org/wiki/Stada_Arzneimittel" },
  merckkgaa: { name: "Merck KGaA", kind: "pharma", country: "DE", verify: "https://en.wikipedia.org/wiki/Merck_Group" },
  merz: { name: "Merz Pharma", kind: "pharma", country: "DE", verify: "https://en.wikipedia.org/wiki/Merz_Pharma" },
  queisser: { name: "Queisser Pharma", kind: "pharma", country: "DE", verify: "https://duckduckgo.com/?q=who+owns+Queisser+Pharma+Doppelherz" },
  astrazeneca: { name: "AstraZeneca", kind: "pharma", country: "GB", verify: "https://en.wikipedia.org/wiki/AstraZeneca" },
  lilly: { name: "Eli Lilly", kind: "pharma", country: "US", verify: "https://en.wikipedia.org/wiki/Eli_Lilly_and_Company" },
  novo: { name: "Novo Nordisk", kind: "pharma", country: "DK", verify: "https://en.wikipedia.org/wiki/Novo_Nordisk" },
  roche: { name: "Roche", kind: "pharma", country: "CH", verify: "https://en.wikipedia.org/wiki/Hoffmann-La_Roche" },
  harbin: { name: "Harbin Pharmaceutical Group", kind: "pharma", country: "CN", verify: "https://en.wikipedia.org/wiki/Harbin_Pharmaceutical_Group" },
  gnc: { name: "GNC", kind: "retailer", parent: "harbin", lineage: "owned by Harbin Pharmaceutical Group since 2020", country: "US", verify: "https://en.wikipedia.org/wiki/GNC_(company)" },
  byhealth: { name: "BY-HEALTH", kind: "conglomerate", lineage: "a Chinese dietary-supplement group", country: "CN", verify: "https://duckduckgo.com/?q=who+owns+BY-HEALTH" },
  nestle: { name: "Nestlé (Nestlé Health Science)", kind: "conglomerate", lineage: "a food group; its health-science arm bought the brand. Not a drug maker, but not independent", country: "CH", verify: "https://en.wikipedia.org/wiki/Nestl%C3%A9_Health_Science" },
  unilever: { name: "Unilever", kind: "conglomerate", lineage: "a consumer-goods group; not a drug maker, but not independent", country: "GB", verify: "https://en.wikipedia.org/wiki/Unilever" },
  clorox: { name: "Clorox", kind: "conglomerate", lineage: "a consumer-goods group; not a drug maker, but not independent", country: "US", verify: "https://en.wikipedia.org/wiki/Clorox" },
  kirin: { name: "Kirin Holdings", kind: "conglomerate", lineage: "a Japanese beverage group", country: "JP", verify: "https://en.wikipedia.org/wiki/Kirin_Company" },
  hh: { name: "Health and Happiness (H&H) Group", kind: "conglomerate", country: "HK", verify: "https://duckduckgo.com/?q=who+owns+Swisse+H%26H+Group" },
  jamieson: { name: "Jamieson Wellness", kind: "conglomerate", lineage: "a Canadian public vitamin company", country: "CA", verify: "https://en.wikipedia.org/wiki/Jamieson_Wellness" },
  kroger: { name: "Kroger", kind: "retailer", country: "US", verify: "https://en.wikipedia.org/wiki/Kroger" },
  dsm: { name: "dsm-firmenich", kind: "conglomerate", lineage: "a Dutch-Swiss nutrition and chemicals group", country: "NL", verify: "https://en.wikipedia.org/wiki/DSM-Firmenich" },
  adm: { name: "ADM (Archer-Daniels-Midland)", kind: "conglomerate", lineage: "an agricultural commodities group", country: "US", verify: "https://en.wikipedia.org/wiki/Archer_Daniels_Midland" },
  lcatterton: { name: "L Catterton", kind: "equity", lineage: "a private-equity firm (backed by LVMH)", country: "US", verify: "https://en.wikipedia.org/wiki/L_Catterton" },
  newmountain: { name: "New Mountain Capital", kind: "equity", lineage: "a private-equity firm", country: "US", verify: "https://en.wikipedia.org/wiki/New_Mountain_Capital" },
  hggc: { name: "HGGC", kind: "equity", lineage: "a private-equity firm", country: "US", verify: "https://duckduckgo.com/?q=who+owns+Solaray+Better+Being+Co" },
  amway: { name: "Amway", kind: "conglomerate", lineage: "a multi-level marketing group", country: "US", verify: "https://en.wikipedia.org/wiki/Amway" },
  kikkoman: { name: "Kikkoman", kind: "conglomerate", lineage: "a Japanese food group", country: "JP", verify: "https://en.wikipedia.org/wiki/Kikkoman" },
  pipingrock: { name: "Piping Rock Health Products", kind: "independent", country: "US", verify: "https://duckduckgo.com/?q=who+owns+Piping+Rock+Health+Products" },
  schiff: { name: "Schiff Nutrition", kind: "pharma", parent: "reckitt", lineage: "bought by Reckitt in 2012", country: "US", verify: "https://en.wikipedia.org/wiki/Schiff_Nutrition_International" },
  meadjohnson: { name: "Mead Johnson", kind: "pharma", parent: "reckitt", lineage: "bought by Reckitt in 2017", country: "US", verify: "https://en.wikipedia.org/wiki/Mead_Johnson" },
  ihealth: { name: "i-Health", kind: "conglomerate", parent: "dsm", lineage: "a dsm-firmenich subsidiary", country: "US", verify: "https://duckduckgo.com/?q=who+owns+Culturelle+i-Health+DSM" },
  natrol: { name: "Natrol", kind: "conglomerate", parent: "jamieson", lineage: "bought by Jamieson Wellness in 2025", country: "US", verify: "https://duckduckgo.com/?q=who+owns+Natrol" },
  better: { name: "Better Being Co.", kind: "equity", parent: "hggc", lineage: "formerly Nutraceutical International; owned by HGGC", country: "US", verify: "https://duckduckgo.com/?q=who+owns+Better+Being+Co" },
  foundation: { name: "Foundation Consumer Healthcare", kind: "pharma", lineage: "an over-the-counter medicine company (Plan B One-Step)", country: "US", verify: "https://duckduckgo.com/?q=Foundation+Consumer+Healthcare+Plan+B" },
  mentholatum: { name: "The Mentholatum Company", kind: "pharma", parent: "rohto", lineage: "owned by Rohto Pharmaceutical since 1988", country: "US", verify: "https://en.wikipedia.org/wiki/Mentholatum" },
  padagis: { name: "Padagis", kind: "pharma", lineage: "Perrigo's former prescription-generics arm, owned by Altaris (private equity)", country: "US", verify: "https://duckduckgo.com/?q=Padagis+Perrigo+Altaris" },
};

// ---- the brands ------------------------------------------------------------------------
// [brand, company]. Matched as whole words, case-insensitively, against the
// product's brand, manufacturer line and title. Longer names are tried first.
const BRANDS = [
  // Kenvue (ex Johnson & Johnson)
  ["Tylenol", "kenvue"], ["Motrin", "kenvue"], ["Benadryl", "kenvue"], ["Zyrtec", "kenvue"], ["Sudafed", "kenvue"], ["Pepcid", "kenvue"], ["Imodium", "kenvue"], ["Nicorette", "kenvue"], ["NicoDerm", "kenvue"], ["Zarbee's", "kenvue"], ["Zarbees", "kenvue"], ["Rhinocort", "kenvue"], ["Lactaid", "kenvue"], ["Mylanta", "kenvue"], ["Rogaine", "kenvue"], ["Bengay", "kenvue"], ["Neosporin", "kenvue"], ["Band-Aid", "kenvue"], ["Listerine", "kenvue"], ["Neutrogena", "kenvue"], ["Aveeno", "kenvue"], ["Visine", "kenvue"], ["Tylenol PM", "kenvue"], ["Children's Tylenol", "kenvue"], ["Johnson's", "kenvue"], ["Desitin", "kenvue"], ["Nizoral", "kenvue"], ["Dr.Ci:Labo", "kenvue"],
  // Haleon (ex GSK / Pfizer consumer)
  ["Advil", "haleon"], ["Panadol", "haleon"], ["Voltaren", "haleon"], ["Centrum", "haleon"], ["Emergen-C", "haleon"], ["Theraflu", "haleon"], ["Excedrin", "haleon"], ["Tums", "haleon"], ["Flonase", "haleon"], ["Robitussin", "haleon"], ["Sensodyne", "haleon"], ["Polident", "haleon"], ["Poligrip", "haleon"], ["Otrivin", "haleon"], ["Nexium 24HR", "haleon"], ["ChapStick", "haleon"], ["Caltrate", "haleon"], ["Preparation H", "haleon"], ["Abreva", "haleon"], ["Fenbid", "haleon"], ["Parodontax", "haleon"], ["Beechams", "haleon"], ["Night Nurse", "haleon"], ["Day Nurse", "haleon"], ["Piriton", "haleon"], ["Zovirax", "haleon"], ["Nicotinell", "haleon"], ["Fenistil", "haleon"], ["Buckley's", "haleon"], ["Dimetapp", "haleon"],
  // Bayer
  ["Aleve", "bayer"], ["Claritin", "bayer"], ["Alka-Seltzer", "bayer"], ["One A Day", "bayer"], ["Flintstones", "bayer"], ["MiraLAX", "bayer"], ["Bayer Aspirin", "bayer"], ["Midol", "bayer"], ["Canesten", "bayer"], ["Bepanthen", "bayer"], ["Berocca", "bayer"], ["Redoxon", "bayer"], ["Supradyn", "bayer"], ["Iberogast", "bayer"], ["Elevit", "bayer"], ["Afrin", "bayer"], ["Lotrimin", "bayer"], ["Phillips'", "bayer"], ["Coricidin", "bayer"], ["Citracal", "bayer"], ["Aspirina", "bayer"], ["Cafiaspirina", "bayer"], ["Talcid", "bayer"], ["Rennie", "bayer"], ["Alka-Seltzer Plus", "bayer"],
  // Opella (ex Sanofi)
  ["Allegra", "opella"], ["Dulcolax", "opella"], ["IcyHot", "opella"], ["Icy Hot", "opella"], ["Gold Bond", "opella"], ["Unisom", "opella"], ["Nasacort", "opella"], ["Xyzal", "opella"], ["Buscopan", "opella"], ["Doliprane", "opella"], ["Essentiale", "opella"], ["Zantac 360", "opella"], ["Cystex", "opella"], ["Selsun Blue", "opella"], ["Enterogermina", "opella"], ["Nature's Own", "opella"], ["Cenovis", "opella"], ["Bisolvon", "opella"], ["Mucosolvan", "opella"], ["Novanuit", "opella"], ["Aspegic", "opella"], ["Telfast", "opella"], ["Phytoxil", "opella"], ["Lactacyd", "opella"],
  // Reckitt
  ["Mucinex", "reckitt"], ["Nurofen", "reckitt"], ["Strepsils", "reckitt"], ["Gaviscon", "reckitt"], ["Airborne", "reckitt"], ["Delsym", "reckitt"], ["Lemsip", "reckitt"], ["Durex", "reckitt"], ["Dettol", "reckitt"], ["Lysol", "reckitt"], ["Clearasil", "reckitt"], ["Scholl", "reckitt"], ["Enfamil", "meadjohnson"], ["Move Free", "schiff"], ["MegaRed", "schiff"], ["Digestive Advantage", "schiff"], ["Neuriva", "schiff"], ["Schiff", "schiff"], ["Bonjela", "reckitt"], ["Senokot", "reckitt"], ["Fybogel", "reckitt"], ["Optrex", "reckitt"], ["Dr. Scholl's", "reckitt"],
  // Procter & Gamble
  ["Vicks", "pg"], ["NyQuil", "pg"], ["DayQuil", "pg"], ["ZzzQuil", "pg"], ["Pepto-Bismol", "pg"], ["Pepto Bismol", "pg"], ["Align Probiotic", "pg"], ["Metamucil", "pg"], ["Prilosec OTC", "pg"], ["Prilosec", "pg"], ["Crest", "pg"], ["Oral-B", "pg"], ["New Chapter", "pg"], ["Nervive", "pg"], ["Voost", "pg"], ["Head & Shoulders", "pg"], ["Fixodent", "pg"], 
  // Perrigo and store brands it makes
  ["Perrigo", "perrigo"], ["Compeed", "perrigo"], ["Mederma", "perrigo"], ["Nasonex 24HR", "perrigo"], ["Opcon-A", "perrigo"], ["Abtei", "perrigo"], ["ACO", "perrigo"], ["Jungle Formula", "perrigo"], ["Solpadeine", "perrigo"], ["Paramol", "perrigo"], ["XLS Medical", "perrigo"], ["Lactulose", "perrigo"], ["Good Sense", "perrigo"], ["GoodSense", "perrigo"],
  // Pharmavite (Otsuka)
  ["Nature Made", "pharmavite"], ["MegaFood", "pharmavite"], ["Uqora", "pharmavite"], ["Equelle", "pharmavite"], ["Pharmavite", "pharmavite"],
  // Church & Dwight
  ["Vitafusion", "churchdwight"], ["L'il Critters", "churchdwight"], ["Lil Critters", "churchdwight"], ["Zicam", "churchdwight"], ["Orajel", "churchdwight"], ["Arm & Hammer", "churchdwight"], ["Batiste", "churchdwight"], ["Therabreath", "churchdwight"], ["Hero Cosmetics", "churchdwight"], ["Sterimar", "churchdwight"], ["Femfresh", "churchdwight"], ["Anusol", "churchdwight"], ["Nair", "churchdwight"], ["Trojan", "churchdwight"], ["First Response", "churchdwight"],
  // Prestige Consumer Healthcare
  ["Dramamine", "prestige"], ["Chloraseptic", "prestige"], ["Luden's", "prestige"], ["Clear Eyes", "prestige"], ["Monistat", "prestige"], ["Compound W", "prestige"], ["Summer's Eve", "prestige"], ["BC Powder", "prestige"], ["Goody's", "prestige"], ["DenTek", "prestige"], ["Gaviscon", "prestige"], ["Debrox", "prestige"], ["Little Remedies", "prestige"], ["Boudreaux's", "prestige"], ["Fess", "prestige"], ["Hydralyte", "prestige"], ["TheraTears", "prestige"], ["Beano", "prestige"], ["Dermoplast", "prestige"], 
  // Abbott
  ["Pedialyte", "abbott"], ["Similac", "abbott"], ["Ensure", "abbott"], ["Glucerna", "abbott"], ["FreeStyle", "abbott"], ["Nepro", "abbott"], ["PediaSure", "abbott"], ["ZonePerfect", "abbott"], ["Brufen", "abbott"], ["Duphalac", "abbott"],
  // Bausch, Alcon, AbbVie/Allergan
  ["PreserVision", "bauschlomb"], ["Ocuvite", "bauschlomb"], ["Biotrue", "bauschlomb"], ["Lumify", "bauschlomb"], ["ReNu", "bauschlomb"], ["Alaway", "bauschlomb"], ["Refresh Tears", "allergan"], ["Refresh Optive", "allergan"], ["Systane", "alcon"], ["Opti-Free", "alcon"], ["Clear Care", "alcon"], ["Restasis", "allergan"], ["Botox", "allergan"],
  // Generic-drug makers whose own labels sell OTC
  ["Teva", "teva"], ["Sandoz", "sandoz"], ["Mylan", "viatris"], ["Viatris", "viatris"], ["Hikma", "hikma"], ["Stada", "stada"], ["Grippostad", "stada"], ["Ladival", "stada"], ["Hedrin", "stada"], ["Cipla", "cipla"], ["Sun Pharma", "sunpharma"], ["Taro", "sunpharma"], ["Dr. Reddy's", "drreddys"], ["Lupin", "lupin"], ["Zydus", "zydus"], ["Glenmark", "glenmark"], ["Padagis", "padagis"],
  // Japanese OTC houses
  ["Pabron", "taisho"], ["Lipovitan", "taisho"], ["Taisho", "taisho"], ["Cabagin", "kowa"], ["Kowa", "kowa"], ["Rohto", "rohto"], ["Mentholatum", "mentholatum"], ["Deep Heat", "mentholatum"], ["Salonpas", "hisamitsu"], ["Loxonin", "daiichi"], ["Alinamin", "takeda"], ["Pocari Sweat", "otsuka"], ["Oronamin", "otsuka"],
  // Other pharma-owned consumer brands
  ["Florastor", "biocodex"], ["Bion3", "merckkgaa"], ["Nasivin", "merckkgaa"], ["Neurobion", "pg"], ["Seven Seas", "merckkgaa"], ["tetesept", "merz"], ["Merz Spezial", "merz"], ["Doppelherz", "queisser"], ["Protefix", "queisser"], ["Plan B One-Step", "foundation"], ["Plan B", "foundation"], ["Nasonex", "organon"], ["Nature's Way", "schwabe"], ["Natures Way", "schwabe"], ["Enzymatic Therapy", "schwabe"], ["Integrative Therapeutics", "schwabe"], ["Umcka", "schwabe"], ["Sambucol", "pharmacare"], ["Nasivion", "pg"],
  // Conglomerates, equity and retailers (not drug makers, not independent)
  ["Garden of Life", "nestle"], ["Pure Encapsulations", "nestle"], ["Nature's Bounty", "nestle"], ["Natures Bounty", "nestle"], ["Solgar", "nestle"], ["Puritan's Pride", "nestle"], ["Osteo Bi-Flex", "nestle"], ["Vital Proteins", "nestle"], ["Orgain", "nestle"], ["Persona Nutrition", "nestle"], ["Sundown", "nestle"], ["Ester-C", "nestle"], ["Douglas Laboratories", "nestle"], ["Wobenzym", "nestle"], ["Olly", "unilever"], ["Liquid I.V.", "unilever"], ["Liquid IV", "unilever"], ["SmartyPants", "unilever"], ["Nutrafol", "unilever"], ["Onnit", "unilever"], ["Pukka", "unilever"], ["Natural Vitality", "clorox"], ["Renew Life", "clorox"], ["RenewLife", "clorox"], ["Rainbow Light", "clorox"], ["NeoCell", "clorox"], ["Blackmores", "kirin"], ["Swisse", "hh"], ["Jamieson", "jamieson"], ["Natrol", "natrol"], ["Webber Naturals", "jamieson"], ["Vitacost", "kroger"], ["Culturelle", "ihealth"], ["Thorne", "lcatterton"], ["Jarrow Formulas", "newmountain"], ["Jarrow", "newmountain"], ["Solaray", "better"], ["KAL", "better"], ["Zand", "better"], ["Nutrilite", "amway"], ["Country Life", "kikkoman"], ["GNC", "gnc"], ["Nature's Truth", "pipingrock"], ["BY-HEALTH", "byhealth"], ["Dabur", "dabur"], ["Himalaya", "himalaya"],
];
COMPANIES.organon = { name: "Organon", kind: "pharma", lineage: "spun out of Merck & Co. in 2021", country: "US", verify: "https://en.wikipedia.org/wiki/Organon_%26_Co." };
COMPANIES.pharmacare = { name: "PharmaCare Laboratories", kind: "pharma", lineage: "an Australian consumer-health and OTC maker", country: "AU", verify: "https://duckduckgo.com/?q=who+owns+Sambucol+PharmaCare" };

const sortedBrands = BRANDS.slice().sort((left, right) => right[0].length - left[0].length);
const escapeRegExp = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const brandPatterns = sortedBrands.map(([brand, company]) => ({ brand, company, pattern: new RegExp("(^|[^a-z0-9])" + escapeRegExp(brand.toLowerCase()).replace(/'/g, "['’]?") + "($|[^a-z0-9])", "i") }));

// Company names as they appear on a "manufacturer" line.
const COMPANY_NAMES = [
  ["johnson & johnson", "jnj"], ["johnson and johnson", "jnj"], ["j&j", "jnj"], ["kenvue", "kenvue"], ["mcneil", "kenvue"], ["glaxosmithkline", "gsk"], ["gsk", "gsk"], ["haleon", "haleon"], ["pfizer", "pfizer"], ["bayer", "bayer"], ["sanofi", "sanofi"], ["opella", "opella"], ["chattem", "opella"], ["reckitt", "reckitt"], ["rb health", "reckitt"], ["procter & gamble", "pg"], ["procter and gamble", "pg"], ["p&g", "pg"], ["perrigo", "perrigo"], ["teva", "teva"], ["novartis", "novartis"], ["sandoz", "sandoz"], ["abbvie", "abbvie"], ["allergan", "allergan"], ["abbott", "abbott"], ["otsuka", "otsuka"], ["pharmavite", "pharmavite"], ["viatris", "viatris"], ["mylan", "viatris"], ["bausch", "bausch"], ["alcon", "alcon"], ["prestige consumer", "prestige"], ["prestige brands", "prestige"], ["church & dwight", "churchdwight"], ["church and dwight", "churchdwight"], ["schwabe", "schwabe"], ["biocodex", "biocodex"], ["boehringer", "boehringer"], ["takeda", "takeda"], ["daiichi", "daiichi"], ["taisho", "taisho"], ["kowa", "kowa"], ["rohto", "rohto"], ["mentholatum", "mentholatum"], ["hisamitsu", "hisamitsu"], ["sun pharma", "sunpharma"], ["cipla", "cipla"], ["dr. reddy", "drreddys"], ["dr reddy", "drreddys"], ["lupin", "lupin"], ["zydus", "zydus"], ["glenmark", "glenmark"], ["hikma", "hikma"], ["stada", "stada"], ["merck kgaa", "merckkgaa"], ["merz", "merz"], ["queisser", "queisser"], ["astrazeneca", "astrazeneca"], ["eli lilly", "lilly"], ["novo nordisk", "novo"], ["roche", "roche"], ["harbin", "harbin"], ["nestle", "nestle"], ["nestlé", "nestle"], ["unilever", "unilever"], ["clorox", "clorox"], ["kirin", "kirin"], ["jamieson", "jamieson"], ["kroger", "kroger"], ["dsm", "dsm"], ["l catterton", "lcatterton"], ["new mountain", "newmountain"], ["amway", "amway"], ["kikkoman", "kikkoman"], ["schiff", "schiff"], ["mead johnson", "meadjohnson"], ["organon", "organon"],
];

function chainFor(companyId) {
  const chain = [];
  let id = companyId;
  const seen = new Set();
  while (id && COMPANIES[id] && !seen.has(id)) {
    seen.add(id);
    const company = COMPANIES[id];
    chain.push({ id, name: company.name, kind: company.kind, country: company.country, note: company.lineage || "", verify: company.verify });
    id = company.parent;
  }
  return chain;
}

// The verdict for a chain: pharma if any layer makes drugs or came out of a
// company that does; otherwise the strongest non-independent kind present.
function verdictFor(chain) {
  if (chain.some((layer) => layer.kind === "pharma" || layer.kind === "consumer-health")) return "pharma";
  if (chain.some((layer) => layer.kind === "equity")) return "equity";
  if (chain.some((layer) => layer.kind === "conglomerate" || layer.kind === "retailer")) return "conglomerate";
  return "independent";
}

Shield.pharmaLookup = function pharmaLookup(hints) {
  const fields = [hints.brand, hints.manufacturer, hints.title].map((value) => String(value || ""));
  // Brand names, in the brand field first, then the manufacturer line, then the title.
  for (const field of fields) {
    if (!field) continue;
    for (const { brand, company, pattern } of brandPatterns) {
      if (pattern.test(field)) {
        const chain = chainFor(company);
        return { matched: brand, via: field === fields[0] ? "brand" : field === fields[1] ? "manufacturer" : "title", chain, verdict: verdictFor(chain) };
      }
    }
  }
  // A company named outright on the manufacturer line.
  const manufacturer = (fields[1] + " " + String(hints.seller || "")).toLowerCase();
  for (const [name, company] of COMPANY_NAMES) {
    if (manufacturer.includes(name)) {
      const chain = chainFor(company);
      return { matched: COMPANIES[company].name, via: "manufacturer", chain, verdict: verdictFor(chain) };
    }
  }
  return null;
};

// ---- what the product is for -------------------------------------------------------
// Categories by the words on the box; each with herbal alternatives.
const CATEGORIES = [
  { id: "pain", label: "pain and fever relief", test: /\b(ibuprofen|acetaminophen|paracetamol|naproxen|aspirin|pain relie|painkiller|fever reduc|headache|migraine|analgesic|back pain|muscle ache|tylenol|advil|motrin|aleve|excedrin|nurofen|panadol|doliprane|voltaren|diclofenac)\b/i,
    herbal: [
      { name: "White willow bark", why: "the plant aspirin came from; salicin in the bark" },
      { name: "Turmeric (curcumin)", why: "the root used for aches and inflammation" },
      { name: "Boswellia (frankincense)", why: "resin extract used for joint and muscle pain" },
      { name: "Ginger root", why: "used for aches, nausea and inflammation" },
      { name: "Arnica (topical)", why: "a cream or gel for bruises and sore muscles; outside only" },
      { name: "Devil's claw", why: "a southern African root used for back and joint pain" },
      { name: "Feverfew", why: "a traditional herb for migraines" },
    ] },
  { id: "allergy", label: "allergy relief", test: /\b(loratadine|cetirizine|fexofenadine|levocetirizine|diphenhydramine|antihistamine|allerg(y|ies)|hay ?fever|pollen|fluticasone|nasal spray|claritin|zyrtec|allegra|xyzal|benadryl|flonase|nasacort|piriton|telfast)\b/i,
    herbal: [
      { name: "Stinging nettle leaf", why: "freeze-dried nettle is the classic herbal antihistamine" },
      { name: "Quercetin with bromelain", why: "a plant flavonoid (from onions, apples, capers) that steadies mast cells" },
      { name: "Butterbur (PA-free)", why: "a European herb studied against hay fever; choose PA-free extracts" },
      { name: "Eyebright", why: "for itchy, watery eyes" },
      { name: "Saline nasal rinse", why: "salt water, no drug at all, for a stuffed nose" },
    ] },
  { id: "cold", label: "cough, cold and flu", test: /\b(cough|cold and flu|cold & flu|flu relief|decongestant|guaifenesin|dextromethorphan|pseudoephedrine|phenylephrine|expectorant|sore throat|lozenge|mucinex|robitussin|theraflu|dayquil|nyquil|vicks|sudafed|strepsils|delsym|lemsip|pabron|contac|beechams|night nurse)\b/i,
    herbal: [
      { name: "Elderberry syrup", why: "the berry traditionally taken at the first sign of a cold" },
      { name: "Thyme and ivy leaf", why: "the two herbs in European cough syrups" },
      { name: "Marshmallow root", why: "soothes a raw throat and a dry cough" },
      { name: "Slippery elm lozenges", why: "coats the throat" },
      { name: "Echinacea", why: "the prairie herb for the start of a cold" },
      { name: "Andrographis", why: "the Ayurvedic 'king of bitters' for colds" },
      { name: "Eucalyptus and peppermint", why: "steam or a chest rub for a blocked nose" },
      { name: "Licorice root", why: "for a cough and a sore throat; not for long stretches or with high blood pressure" },
    ] },
  { id: "immune", label: "immune support", test: /\b(immune|immunity|vitamin c|zinc lozenge|emergen-c|airborne|zicam|cold-eeze|elderberry)\b/i,
    herbal: [
      { name: "Elderberry", why: "berry extract or syrup" },
      { name: "Echinacea", why: "root or flower tincture" },
      { name: "Astragalus root", why: "the Chinese tonic root for long-term immune strength" },
      { name: "Reishi and turkey tail mushrooms", why: "medicinal mushrooms grown by independent growers" },
      { name: "Amla and acerola", why: "whole-fruit vitamin C, not synthetic ascorbic acid" },
      { name: "Olive leaf extract", why: "a Mediterranean antimicrobial herb" },
    ] },
  { id: "sleep", label: "sleep aids", test: /\b(sleep aid|sleeping|insomnia|melatonin|doxylamine|diphenhydramine|unisom|zzzquil|nytol|sominex|restful sleep|fall asleep)\b/i,
    herbal: [
      { name: "Valerian root", why: "the traditional European sleep herb" },
      { name: "Chamomile", why: "the bedtime tea" },
      { name: "Passionflower", why: "for a racing mind at night" },
      { name: "Lemon balm", why: "calming, often paired with valerian" },
      { name: "Lavender", why: "oil or capsules for restlessness" },
      { name: "Hops", why: "the bitter cone, a sedative long before beer" },
      { name: "Ashwagandha", why: "the Ayurvedic root for stress and sleep" },
    ] },
  { id: "digestion", label: "stomach, heartburn and digestion", test: /\b(antacid|heartburn|acid reflux|indigestion|omeprazole|esomeprazole|famotidine|ranitidine|calcium carbonate|bismuth|laxative|constipation|diarrhea|diarrhoea|loperamide|polyethylene glycol|bisacodyl|psyllium|fiber supplement|fibre supplement|bloating|gas relief|simethicone|probiotic|tums|pepto|gaviscon|prilosec|nexium|pepcid|zantac|miralax|dulcolax|imodium|metamucil|align|culturelle|florastor|rennie|buscopan|iberogast|senokot|fybogel)\b/i,
    herbal: [
      { name: "Ginger root", why: "for nausea and a slow stomach" },
      { name: "Peppermint oil (enteric capsules)", why: "the best-studied herb for IBS cramps and bloating" },
      { name: "DGL licorice", why: "chewable deglycyrrhizinated licorice for heartburn" },
      { name: "Slippery elm and marshmallow root", why: "mucilage that coats an irritated gut" },
      { name: "Fennel and chamomile", why: "for gas and cramps; the classic gripe-water herbs" },
      { name: "Psyllium husk (plain)", why: "the same fibre as the branded powders, sold by the pound" },
      { name: "Triphala", why: "the Ayurvedic three-fruit blend for regularity" },
      { name: "Artichoke leaf", why: "for bile flow and indigestion after rich food" },
      { name: "Aloe vera inner-leaf juice", why: "for reflux and a sluggish gut" },
    ] },
  { id: "vitamins", label: "vitamins and multivitamins", test: /\b(multivitamin|multi-vitamin|vitamin [a-k]\b|vitamin d3?|b12|b-complex|b complex|folic acid|folate|prenatal|gummy vitamin|gummies|iron supplement|calcium|magnesium|omega-3|omega 3|fish oil|centrum|one a day|nature made|flintstones|vitafusion|olly|smartypants|berocca|supradyn|redoxon)\b/i,
    herbal: [
      { name: "Moringa leaf", why: "a whole-leaf powder dense in vitamins A, C, iron and calcium" },
      { name: "Amla (Indian gooseberry)", why: "whole-fruit vitamin C" },
      { name: "Nettle leaf", why: "iron, calcium and minerals in a leaf" },
      { name: "Spirulina and chlorella", why: "algae for B vitamins, iron and protein" },
      { name: "Rosehip", why: "vitamin C and bioflavonoids from the fruit" },
      { name: "Sea buckthorn", why: "omegas and vitamins from the berry" },
      { name: "Alfalfa and dandelion leaf", why: "mineral-rich greens" },
      { name: "Algae oil (vegan omega-3)", why: "DHA from algae rather than fish, from independent makers" },
    ] },
  { id: "joint", label: "joint and muscle care", test: /\b(joint (health|support|pain)|arthritis|glucosamine|chondroitin|msm|osteo bi-flex|move free|cartilage|mobility|muscle rub|liniment|deep heat|salonpas|bengay|icy ?hot|tiger balm)\b/i,
    herbal: [
      { name: "Turmeric (curcumin) with black pepper", why: "the standard herbal anti-inflammatory" },
      { name: "Boswellia", why: "frankincense resin for stiff joints" },
      { name: "Devil's claw", why: "for arthritis and low back pain" },
      { name: "Ginger", why: "fresh, dried or as a rub" },
      { name: "Arnica or comfrey (topical)", why: "creams for sore joints; outside only" },
      { name: "Cayenne (capsaicin) cream", why: "the pepper's heat for aching joints" },
      { name: "Nettle", why: "for arthritic pain, taken as tea or capsules" },
    ] },
  { id: "skin", label: "skin, cuts and rashes", test: /\b(antibiotic ointment|neosporin|bacitracin|hydrocortisone|cortizone|anti-itch|itch relief|rash|eczema|antifungal|athlete's foot|clotrimazole|miconazole|lotrimin|canesten|wound|first aid cream|bepanthen|aquaphor|diaper rash|desitin|cold sore|abreva|zovirax)\b/i,
    herbal: [
      { name: "Calendula salve", why: "the marigold for cuts, scrapes and rashes" },
      { name: "Tea tree oil", why: "an antimicrobial for fungal skin and spots" },
      { name: "Plantain leaf salve", why: "the weed in every lawn, for bites and stings" },
      { name: "Comfrey salve (unbroken skin)", why: "for bruises and sprains" },
      { name: "Chickweed", why: "cooling, for itchy rashes and eczema" },
      { name: "Aloe vera gel", why: "for burns and sun" },
      { name: "Manuka honey", why: "for wounds that are slow to close" },
      { name: "Witch hazel", why: "an astringent for rashes and irritation" },
      { name: "Lemon balm (topical)", why: "the herb studied for cold sores" },
    ] },
  { id: "eyes", label: "eye drops", test: /\b(eye drops|dry eye|red eye|eye relief|redness relie|lubricant eye|artificial tears|visine|refresh|systane|clear eyes|lumify|optrex)\b/i,
    herbal: [
      { name: "Eyebright (euphrasia) drops", why: "the herb named for its use on tired, red eyes; homeopathic or herbal preparations" },
      { name: "Chamomile compress", why: "a cooled tea bag over closed eyes" },
      { name: "Bilberry", why: "the berry taken for eye health" },
      { name: "Preservative-free saline", why: "plain, no drug" },
    ] },
  { id: "women", label: "menstrual and women's health", test: /\b(menstrual|period pain|cramps|pms|midol|pamprin|yeast infection|monistat|vaginal|menopause|hot flash|hot flush|estroven)\b/i,
    herbal: [
      { name: "Cramp bark", why: "named for what it is used for" },
      { name: "Ginger", why: "studied against period pain" },
      { name: "Chasteberry (vitex)", why: "the European herb for PMS and cycle balance" },
      { name: "Raspberry leaf", why: "the uterine tonic tea" },
      { name: "Dong quai", why: "the Chinese women's root" },
      { name: "Black cohosh and sage", why: "for menopausal hot flushes" },
    ] },
  { id: "urinary", label: "urinary health", test: /\b(urinary|uti\b|bladder|cystitis|azo\b|cystex|phenazopyridine|cranberry supplement)\b/i,
    herbal: [
      { name: "Cranberry (whole fruit extract)", why: "the classic; look for PAC content" },
      { name: "D-mannose", why: "a plant sugar that keeps bacteria from sticking" },
      { name: "Uva ursi (bearberry)", why: "the traditional urinary antiseptic, short courses only" },
      { name: "Corn silk and marshmallow root", why: "soothing for an irritated bladder" },
      { name: "Nettle and dandelion leaf", why: "gentle diuretics" },
    ] },
  { id: "stress", label: "stress, mood and focus", test: /\b(stress relief|anxiety|mood support|calm(ing)?|focus|nootropic|energy support|adrenal|neuriva|prevagen)\b/i,
    herbal: [
      { name: "Ashwagandha", why: "the Ayurvedic adaptogen for stress" },
      { name: "Rhodiola rosea", why: "the Arctic root for fatigue and focus" },
      { name: "Holy basil (tulsi)", why: "calming tea" },
      { name: "Lemon balm", why: "for nervous tension" },
      { name: "St. John's wort", why: "the traditional mood herb; it interacts with many drugs, so check first" },
      { name: "Lion's mane mushroom", why: "for memory and focus" },
      { name: "Ginkgo and bacopa", why: "the two classic memory herbs" },
    ] },
];

// Independent herbal makers: companies with no pharmaceutical, conglomerate
// or private-equity parent, as far as the public record shows. Each gets a
// product-search link on its own site and a link to check who owns it.
const HERBAL_MAKERS = [
  { name: "Gaia Herbs", site: "gaiaherbs.com", country: "US", note: "privately held, grows much of its own herbs in North Carolina" },
  { name: "Herb Pharm", site: "herb-pharm.com", country: "US", note: "employee-owned, Oregon" },
  { name: "Traditional Medicinals", site: "traditionalmedicinals.com", country: "US", note: "independent, California; herbal teas" },
  { name: "Mountain Rose Herbs", site: "mountainroseherbs.com", country: "US", note: "independent, employee-owned since 2023; bulk herbs" },
  { name: "Oregon's Wild Harvest", site: "oregonswildharvest.com", country: "US", note: "family-owned, grows its own" },
  { name: "WishGarden Herbs", site: "wishgardenherbs.com", country: "US", note: "independent, Colorado; tinctures" },
  { name: "Nature's Answer", site: "naturesanswer.com", country: "US", note: "family-owned (Bio-Botanica), New York" },
  { name: "Banyan Botanicals", site: "banyanbotanicals.com", country: "US", note: "independent Ayurvedic maker" },
  { name: "Organic India", site: "organicindia.com", country: "IN", note: "independent; tulsi, triphala, ashwagandha" },
  { name: "Host Defense", site: "hostdefense.com", country: "US", note: "Fungi Perfecti, founder-owned; mushrooms" },
  { name: "Starwest Botanicals", site: "starwest-botanicals.com", country: "US", note: "independent bulk herbs" },
  { name: "Frontier Co-op", site: "frontiercoop.com", country: "US", note: "a member-owned cooperative" },
  { name: "Pukka (check)", site: "pukkaherbs.com", country: "GB", note: "owned by Unilever since 2017; listed so you know", skip: true },
  { name: "Napiers the Herbalists", site: "napiers.net", country: "GB", note: "independent, Edinburgh, since 1860" },
  { name: "Baldwins", site: "baldwins.co.uk", country: "GB", note: "independent, London, since 1844" },
  { name: "A. Vogel (Bioforce)", site: "avogel.co.uk", country: "CH", note: "family-held Swiss herbal house" },
  { name: "Salus (Floradix)", site: "salus.de", country: "DE", note: "family-held Bavarian herbal company" },
  { name: "Herbaria", site: "herbaria.com", country: "DE", note: "independent, Bavaria" },
  { name: "Arkopharma", site: "arkopharma.com", country: "FR", note: "a French phytotherapy maker; owned by Montagu (private equity) since 2018", skip: true },
  { name: "Naturalma", site: "naturalma.com", country: "IT", note: "independent, Italy" },
  { name: "Hawaii Pharm", site: "hawaiipharm.com", country: "US", note: "independent; tinctures" },
  { name: "Urban Moonshine", site: "urbanmoonshine.com", country: "US", note: "independent, Vermont; bitters and tonics" },
  { name: "HerbEra", site: "herbera.com", country: "US", note: "independent; tinctures" },
  { name: "NOW Foods", site: "nowfoods.com", country: "US", note: "family-owned since 1968 (the Richard family); herbs and vitamins" },
  { name: "Nordic Naturals", site: "nordicnaturals.com", country: "US", note: "privately held; fish and algae oils" },
  { name: "Bluebonnet Nutrition", site: "bluebonnetnutrition.com", country: "US", note: "family-owned, Texas" },
  { name: "Life Extension", site: "lifeextension.com", country: "US", note: "privately held, Florida" },
  { name: "Yogi Tea", site: "yogiproducts.com", country: "US", note: "East West Tea Company, independent" },
  { name: "Buddha Teas", site: "buddhateas.com", country: "US", note: "independent" },
  { name: "Four Sigmatic", site: "foursigmatic.com", country: "US", note: "founder-owned; mushrooms" },
  { name: "Ancient Nutrition", site: "ancientnutrition.com", country: "US", note: "founder-owned" },
  { name: "MaryRuth's", site: "maryruthorganics.com", country: "US", note: "founder-owned" },
  { name: "Seeking Health", site: "seekinghealth.com", country: "US", note: "founder-owned" },
  { name: "Standard Process", site: "standardprocess.com", country: "US", note: "family-owned since 1929, Wisconsin" },
  { name: "Mediherb (Standard Process)", site: "mediherb.com", country: "AU", note: "part of family-owned Standard Process" },
  { name: "Herbs of Gold", site: "herbsofgold.com.au", country: "AU", note: "independent, Australia" },
  { name: "Fusion Health", site: "fusionhealth.com.au", country: "AU", note: "independent, Australia" },
  { name: "Dr. Christopher's", site: "drchristophers.com", country: "US", note: "family-owned, Utah" },
  { name: "Mushroom Revival", site: "mushroomrevival.com", country: "US", note: "independent, Massachusetts" },
  { name: "Wise Woman Herbals", site: "wisewomanherbals.com", country: "US", note: "independent, Oregon" },
  { name: "Vitanica", site: "vitanica.com", country: "US", note: "independent, women's herbal formulas" },
];

Shield.herbalMakers = () => HERBAL_MAKERS.filter((maker) => !maker.skip);

const DRUG_FACTS = /\b(drug facts|active ingredient|supplement facts|uses:? temporarily relieves|warnings:? do not use|directions:? (take|adults)|ask a doctor|keep out of reach of children|pharmac(y|ist)|dosage|tablets?|caplets?|capsules?|softgels?|gummies|lozenges?|syrup|suspension|liquid gels|chewables?|dietary supplement|otc\b|over[- ]the[- ]counter|\d+ ?mg\b|\d+ ?mcg\b|\d+ ?iu\b)\b/i;

Shield.pharmaCheck = function pharmaCheck(hints) {
  const title = String(hints.title || "");
  const words = [title, hints.brand, hints.manufacturer, hints.breadcrumb, hints.facts].map((value) => String(value || "")).join(" \n ");
  const category = CATEGORIES.find((entry) => entry.test.test(words)) || null;
  const factsSeen = DRUG_FACTS.test(words) || /\/(pharmacy|medicine|health|vitamins?|supplements?|otc|drugs?|wellness)\b/i.test(String(hints.breadcrumb || "") + " " + String(hints.url || ""));
  const medicine = Boolean(category) || (factsSeen && /\b(relief|supplement|vitamin|remedy|tablets?|capsules?|gummies|syrup|mg\b)/i.test(words));
  const ownership = Shield.pharmaLookup({ brand: hints.brand, manufacturer: hints.manufacturer, title, seller: hints.seller });
  const makers = Shield.herbalMakers();
  const alternatives = category ? category.herbal.map((herb) => {
    const query = herb.name.replace(/\s*\(.*?\)\s*/g, " ").replace(/\s+/g, " ").trim();
    return {
      herb: herb.name,
      why: herb.why,
      search: `https://duckduckgo.com/?q=${encodeURIComponent(query + " " + categoryWord(category.id))}&ia=web`,
      makers: makers.slice(0, 40).map((maker) => ({ name: maker.name, note: maker.note, country: maker.country, url: `https://duckduckgo.com/?q=${encodeURIComponent("site:" + maker.site + " " + query)}`, home: "https://" + maker.site, verify: `https://duckduckgo.com/?q=${encodeURIComponent("who owns " + maker.name)}` })),
    };
  }) : [];
  return {
    medicine,
    category: category ? { id: category.id, label: category.label } : null,
    ownership,
    alternatives,
    makers: makers.map((maker) => ({ name: maker.name, note: maker.note, country: maker.country, home: "https://" + maker.site, verify: `https://duckduckgo.com/?q=${encodeURIComponent("who owns " + maker.name)}` })),
  };
};

function categoryWord(id) {
  return { pain: "capsules tincture", allergy: "extract", cold: "syrup tincture", immune: "tincture", sleep: "tea capsules", digestion: "capsules", vitamins: "powder capsules", joint: "capsules cream", skin: "salve", eyes: "drops", women: "tincture tea", urinary: "capsules", stress: "tincture" }[id] || "herbal";
}

// Web listings for an herbal alternative from sellers with no pharma parent
// and outside the megastores, with prices where the snippet shows one.
Shield.herbalOffers = async function herbalOffers(category, homeCurrency) {
  const entry = CATEGORIES.find((item) => item.id === category);
  if (!entry || !Shield.webSearch) return [];
  const region = (Shield.REGIONS || []).find((item) => item.currency === homeCurrency) || (Shield.REGIONS || [])[0];
  const picks = entry.herbal.slice(0, 3);
  const results = await Promise.all(picks.map((herb) => Shield.webSearch(herb.name.replace(/\s*\(.*?\)\s*/g, " ").trim() + " " + categoryWord(entry.id) + " buy", region, 2).catch(() => [])));
  const table = await Shield.rates();
  const offers = [];
  const seen = new Set();
  results.forEach((list, index) => {
    for (const result of list) {
      if (result.sponsored || seen.has(result.url) || Shield.isWellKnown(result.host)) continue;
      const owner = Shield.pharmaLookup({ brand: result.host.split(".")[0], title: result.title });
      if (owner && owner.verdict !== "independent") continue;
      if (/(^|\.)(reddit|wikipedia|youtube|facebook|healthline|webmd|medicalnewstoday|verywell|nih\.gov|mayoclinic|drugs\.com|examine)\./i.test(result.host)) continue;
      seen.add(result.url);
      const money = Shield.readMoney(result.snippet + " " + result.title, result.host);
      const converted = money ? Shield.convert(money.price, money.currency, homeCurrency, table) : null;
      offers.push({ herb: picks[index].name, title: result.title.slice(0, 120), url: result.url, store: result.host, price: money ? money.price : null, currency: money ? money.currency : null, total: converted, verify: `https://duckduckgo.com/?q=${encodeURIComponent("who owns " + result.host.split(".").slice(-2, -1)[0])}` });
      if (offers.length >= 12) break;
    }
  });
  return offers;
};

})();
