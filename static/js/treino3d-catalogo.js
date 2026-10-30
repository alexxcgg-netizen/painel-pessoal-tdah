/* Treino ao vivo em 3D: os exercicios que o motor (static/treino3d/treino3d.js) sabe animar e o mapeador
   "nome livre da ficha" -> exercicio do catalogo. Carrega sincrono com os cards (decide se o painel aparece);
   o motor 3D, pesado, so vem quando um card precisa (cards-vivos.js).
   Regra da skill treino-ao-vivo: nome que nao casa com seguranca devolve null e o painel fica escondido -
   melhor nada do que a animacao de outro exercicio.
   O miolo entre CATALOGO-INICIO/FIM e gerado pelo build_app.py do prototipo (docs/prototipos/academia-3d). */
var Treino3DCatalogo = (function () {
  // [grupo, nome, molde, params]
  var CATALOGO = [
    /*CATALOGO-INICIO*/
    ["Peito", "Supino reto com barra", "supino", {}],
    ["Peito", "Supino reto com halteres", "supino", {"halter": true}],
    ["Peito", "Supino inclinado com barra", "supino", {"inclina": 30}],
    ["Peito", "Supino inclinado com halteres", "supino", {"inclina": 30, "halter": true}],
    ["Peito", "Supino declinado com barra", "pe_supino_decl", {}],
    ["Peito", "Supino declinado com halteres", "pe_supino_decl", {"halter": true}],
    ["Peito", "Supino reto no Smith", "pe_smith", {}],
    ["Peito", "Supino inclinado no Smith", "pe_smith", {"inclina": 30}],
    ["Peito", "Supino máquina sentado", "pe_maq_supino", {}],
    ["Peito", "Supino inclinado na máquina", "pe_maq_supino", {"inclina": true}],
    ["Peito", "Supino com pegada fechada", "supino", {"fechada": true, "musc": {"triceps": 1, "peitoral": 0.75, "deltoide": 0.55}}],
    ["Peito", "Supino com halteres pegada neutra", "supino", {"halter": true, "neutra": true, "musc": {"peitoral": 0.9, "triceps": 0.9, "deltoide": 0.6}}],
    ["Peito", "Crucifixo reto com halteres", "crucifixo", {}],
    ["Peito", "Crucifixo inclinado com halteres", "crucifixo", {"inclina": 30}],
    ["Peito", "Crucifixo declinado", "pe_crucifixo_decl", {}],
    ["Peito", "Voador (peck deck)", "pe_voador", {}],
    ["Peito", "Crossover na polia alta", "pe_crossover", {"altura": "alta"}],
    ["Peito", "Crossover na polia média", "pe_crossover", {"altura": "media"}],
    ["Peito", "Crossover na polia baixa", "pe_crossover", {"altura": "baixa"}],
    ["Peito", "Crucifixo na polia deitado", "pe_crucifixo_polia", {}],
    ["Peito", "Pullover com halter", "pe_pullover", {}],
    ["Peito", "Flexão de braço", "pe_flexao", {}],
    ["Peito", "Flexão inclinada", "pe_flexao", {"maosBanco": true}],
    ["Peito", "Flexão declinada", "pe_flexao", {"pesBanco": true}],
    ["Peito", "Flexão diamante", "pe_flexao", {"diamante": true}],
    ["Peito", "Mergulho nas paralelas (peito)", "pe_mergulho", {}],
    ["Peito", "Press de peito no cabo unilateral", "pe_press_cabo", {}],
    ["Costas", "Remada curvada com barra", "remada", {}],
    ["Costas", "Remada curvada supinada", "remada", {"supinada": true}],
    ["Costas", "Levantamento terra", "terra", {}],
    ["Costas", "Remada curvada com halteres", "remada", {"halter": true}],
    ["Costas", "Remada unilateral com halter (serrote)", "co_serrote", {}],
    ["Costas", "Remada cavalinho (T-bar)", "co_tbar", {}],
    ["Costas", "Remada baixa na polia (triângulo)", "co_remada_cabo", {"pega": "triangulo"}],
    ["Costas", "Remada baixa pegada aberta", "co_remada_cabo", {"pega": "aberta"}],
    ["Costas", "Remada na máquina articulada", "co_remada_maq", {}],
    ["Costas", "Remada no Smith", "co_remada_smith", {}],
    ["Costas", "Remada Pendlay", "co_pendlay", {}],
    ["Costas", "Remada invertida", "co_invertida", {}],
    ["Costas", "Puxada frontal pegada aberta", "co_puxada", {"pega": "aberta"}],
    ["Costas", "Puxada frontal pegada fechada", "co_puxada", {"pega": "fechada"}],
    ["Costas", "Puxada com triângulo", "co_puxada", {"pega": "triangulo"}],
    ["Costas", "Puxada supinada", "co_puxada", {"pega": "supinada"}],
    ["Costas", "Puxada unilateral na polia", "co_puxada", {"pega": "neutra", "unilateral": true}],
    ["Costas", "Puxada na máquina articulada", "co_puxada_maq", {}],
    ["Costas", "Pulldown com corda", "co_pulldown", {"corda": true}],
    ["Costas", "Pulldown com barra reta", "co_pulldown", {"corda": false}],
    ["Costas", "Barra fixa pronada", "co_barrafixa", {"pega": "pronada"}],
    ["Costas", "Barra fixa supinada", "co_barrafixa", {"pega": "supinada"}],
    ["Costas", "Barra fixa neutra", "co_barrafixa", {"pega": "neutra"}],
    ["Costas", "Barra fixa assistida", "co_barrafixa", {"assistida": true, "pega": "pronada"}],
    ["Costas", "Levantamento terra sumô", "terra", {"sumo": true, "musc": {"gluteo": 1, "adutor": 0.8, "quadriceps": 0.75, "posterior": 0.7, "lombar": 0.6, "trapezio": 0.45}}],
    ["Costas", "Rack pull", "co_rackpull", {}],
    ["Costas", "Hiperextensão lombar", "co_hiper", {}],
    ["Costas", "Good morning", "co_goodmorning", {}],
    ["Costas", "Superman no solo", "co_superman", {}],
    ["Ombros", "Elevação lateral com halteres", "elevacao", {}],
    ["Ombros", "Elevação frontal com halteres", "elevacao", {"frontal": true}],
    ["Ombros", "Desenvolvimento com barra em pé", "desenvolvimento", {}],
    ["Ombros", "Desenvolvimento com halteres em pé", "desenvolvimento", {"halter": true}],
    ["Ombros", "Desenvolvimento com halteres sentado", "om_pressSent", {}],
    ["Ombros", "Desenvolvimento Arnold", "om_pressSent", {"arnold": true}],
    ["Ombros", "Desenvolvimento no Smith", "om_pressSmith", {}],
    ["Ombros", "Desenvolvimento na máquina", "om_pressMaq", {}],
    ["Ombros", "Push press", "om_pushPress", {}],
    ["Ombros", "Elevação lateral na polia", "om_lateralPolia", {}],
    ["Ombros", "Elevação lateral na máquina", "om_lateralMaq", {}],
    ["Ombros", "Elevação lateral inclinada", "om_lateralInclinada", {}],
    ["Ombros", "Elevação frontal com barra", "elevacao", {"frontal": true, "barra": true}],
    ["Ombros", "Elevação frontal com anilha", "om_frontalAnilha", {}],
    ["Ombros", "Elevação frontal na polia", "om_frontalPolia", {}],
    ["Ombros", "Crucifixo inverso com halteres", "om_invHalter", {}],
    ["Ombros", "Crucifixo inverso na máquina", "om_invMaq", {}],
    ["Ombros", "Crucifixo inverso na polia", "om_invPolia", {}],
    ["Ombros", "Face pull", "om_facePull", {}],
    ["Ombros", "Remada alta com barra", "remadaAlta", {}],
    ["Ombros", "Remada alta na polia", "om_remadaAltaPolia", {}],
    ["Ombros", "Encolhimento com barra", "encolhimento", {}],
    ["Ombros", "Encolhimento com halteres", "encolhimento", {"halter": true}],
    ["Ombros", "Encolhimento no Smith", "om_shrugSmith", {}],
    ["Ombros", "Rotação externa na polia", "om_rotExt", {}],
    ["Ombros", "Y-raise no banco inclinado", "om_yRaise", {}],
    ["Bíceps", "Rosca direta com barra", "rosca", {}],
    ["Bíceps", "Rosca direta com halteres", "rosca", {"halter": true}],
    ["Bíceps", "Rosca martelo", "rosca", {"halter": true, "martelo": true}],
    ["Bíceps", "Rosca direta com barra W", "bi_rosca", {"w": true}],
    ["Bíceps", "Rosca alternada", "bi_alternada", {}],
    ["Bíceps", "Rosca martelo cruzada", "bi_cruzada", {}],
    ["Bíceps", "Rosca concentrada", "bi_concentrada", {}],
    ["Bíceps", "Rosca Scott com barra", "bi_scott", {}],
    ["Bíceps", "Rosca Scott com halter", "bi_scott", {"halter": true}],
    ["Bíceps", "Rosca Scott na máquina", "bi_scott", {"maquina": true}],
    ["Bíceps", "Rosca inclinada com halteres", "bi_inclinada", {}],
    ["Bíceps", "Rosca spider", "bi_spider", {}],
    ["Bíceps", "Rosca na polia baixa", "bi_polia", {}],
    ["Bíceps", "Rosca na polia com corda", "bi_polia", {"corda": true}],
    ["Bíceps", "Rosca bayesian na polia", "bi_bayesian", {}],
    ["Bíceps", "Rosca 21", "bi_21", {}],
    ["Bíceps", "Rosca inversa com barra", "rosca", {"inversa": true, "musc": {"antebraco": 1, "biceps": 0.75}}],
    ["Tríceps", "Tríceps na polia com corda", "tr_polia", {"pega": "corda"}],
    ["Tríceps", "Tríceps na polia com barra reta", "tr_polia", {"pega": "reta"}],
    ["Tríceps", "Tríceps na polia com barra V", "tr_polia", {"pega": "v"}],
    ["Tríceps", "Tríceps na polia pegada invertida", "tr_polia", {"pega": "reta", "invertida": true}],
    ["Tríceps", "Tríceps unilateral na polia", "tr_polia", {"pega": "estribo", "unilateral": true}],
    ["Tríceps", "Tríceps coice na polia", "tr_coice", {"polia": true}],
    ["Tríceps", "Tríceps testa com barra W", "tr_testa", {"tipo": "w"}],
    ["Tríceps", "Tríceps testa com halteres", "tr_testa", {"tipo": "halter"}],
    ["Tríceps", "Tríceps testa na polia", "tr_testa", {"tipo": "polia"}],
    ["Tríceps", "Tríceps francês com halter", "tr_frances", {"tipo": "halter"}],
    ["Tríceps", "Tríceps francês unilateral", "tr_frances", {"tipo": "uni"}],
    ["Tríceps", "Tríceps francês na polia (corda)", "tr_frances", {"tipo": "polia"}],
    ["Tríceps", "Tríceps coice com halter", "tr_coice", {}],
    ["Tríceps", "Mergulho no banco", "tr_mergulho", {}],
    ["Tríceps", "Paralelas (tríceps)", "tr_paralelas", {}],
    ["Tríceps", "Tríceps na máquina", "tr_maquina", {}],
    ["Tríceps", "Supino fechado", "supino", {"fechada": true, "musc": {"triceps": 1, "peitoral": 0.75, "deltoide": 0.55}}],
    ["Tríceps", "JM press", "tr_testa", {"tipo": "jm"}],
    ["Antebraço", "Rosca de punho com barra", "om_punho", {}],
    ["Antebraço", "Rosca de punho inversa", "om_punho", {"inversa": true}],
    ["Antebraço", "Rosca de punho atrás do corpo", "om_punho", {"atras": true}],
    ["Antebraço", "Rolo de punho", "om_rolo", {}],
    ["Antebraço", "Pegada estática (farmer hold)", "om_farmer", {}],
    ["Antebraço", "Pronação e supinação com halter", "om_pronSup", {}],
    ["Quadríceps", "Agachamento livre com barra", "agachamento", {}],
    ["Quadríceps", "Agachamento frontal", "qu_agacha", {"modo": "frontal"}],
    ["Quadríceps", "Agachamento no Smith", "qu_agacha", {"modo": "smith"}],
    ["Quadríceps", "Agachamento goblet", "qu_agacha", {"modo": "goblet"}],
    ["Quadríceps", "Agachamento sumô com halter", "qu_agacha", {"modo": "sumo"}],
    ["Quadríceps", "Agachamento búlgaro", "qu_bulgaro", {}],
    ["Quadríceps", "Agachamento hack na máquina", "qu_hack", {}],
    ["Quadríceps", "Agachamento pistol", "qu_pistol", {}],
    ["Quadríceps", "Agachamento com salto", "qu_salto", {}],
    ["Quadríceps", "Leg press 45°", "qu_legpress", {}],
    ["Quadríceps", "Leg press horizontal", "qu_legpress", {"modo": "horizontal"}],
    ["Quadríceps", "Leg press unilateral", "qu_legpress", {"uni": true}],
    ["Quadríceps", "Cadeira extensora", "qu_extensora", {}],
    ["Quadríceps", "Cadeira extensora unilateral", "qu_extensora", {"uni": true}],
    ["Quadríceps", "Sissy squat", "qu_sissy", {}],
    ["Quadríceps", "Avanço com halteres", "qu_avanco", {}],
    ["Quadríceps", "Avanço com barra", "qu_avanco", {"barra": true}],
    ["Quadríceps", "Avanço andando", "qu_andando", {}],
    ["Quadríceps", "Avanço reverso", "qu_avanco", {"modo": "reverso"}],
    ["Quadríceps", "Passada no Smith", "qu_avanco", {"smith": true}],
    ["Quadríceps", "Subida no banco (step-up)", "qu_stepup", {}],
    ["Quadríceps", "Agachamento na parede (isometria)", "qu_parede", {}],
    ["Posterior de coxa", "Levantamento terra romeno", "terra", {"romeno": true, "musc": {"posterior": 1, "gluteo": 0.95, "lombar": 0.7, "antebraco": 0.45, "trapezio": 0.35}}],
    ["Posterior de coxa", "Stiff com barra", "terra", {"romeno": true, "stiff": true, "musc": {"posterior": 1, "gluteo": 0.85, "lombar": 0.75, "antebraco": 0.45}}],
    ["Posterior de coxa", "Stiff com halteres", "terra", {"halter": true, "romeno": true, "stiff": true, "musc": {"posterior": 1, "gluteo": 0.85, "lombar": 0.75, "antebraco": 0.45}}],
    ["Posterior de coxa", "Stiff unilateral", "po_stiff_uni", {}],
    ["Posterior de coxa", "Mesa flexora", "po_flex_deit", {}],
    ["Posterior de coxa", "Cadeira flexora", "po_flex_sent", {}],
    ["Posterior de coxa", "Flexora em pé unilateral", "po_flex_pe", {}],
    ["Posterior de coxa", "Flexão nórdica", "po_nordica", {}],
    ["Posterior de coxa", "Flexão de joelho na bola", "po_flex_bola", {}],
    ["Posterior de coxa", "Good morning com barra", "po_gm", {}],
    ["Posterior de coxa", "Levantamento terra com pernas rígidas", "terra", {"romeno": true, "stiff": true, "musc": {"posterior": 1, "gluteo": 0.85, "lombar": 0.75, "antebraco": 0.45}}],
    ["Posterior de coxa", "Kettlebell swing", "po_swing", {}],
    ["Glúteos", "Elevação pélvica com barra (hip thrust)", "po_ht", {}],
    ["Glúteos", "Elevação pélvica na máquina", "po_ht_maq", {}],
    ["Glúteos", "Elevação pélvica unilateral", "po_ht", {"uni": true}],
    ["Glúteos", "Ponte de glúteo no solo", "po_ponte", {}],
    ["Glúteos", "Glúteo na polia (coice)", "po_coice", {}],
    ["Glúteos", "Glúteo na máquina (coice)", "po_coice_maq", {}],
    ["Glúteos", "Glúteo 4 apoios com caneleira", "po_4apoios", {}],
    ["Glúteos", "Abdução na polia", "po_abd_polia", {}],
    ["Glúteos", "Cadeira abdutora", "po_abdutora", {}],
    ["Glúteos", "Cadeira adutora", "po_abdutora", {"adutora": true}],
    ["Glúteos", "Abdução deitado com caneleira", "po_abd_deit", {}],
    ["Glúteos", "Abdução com elástico (monster walk)", "po_monster", {}],
    ["Glúteos", "Pull-through na polia", "po_pullthrough", {}],
    ["Glúteos", "Coice com elástico", "po_coice", {"elastico": true}],
    ["Glúteos", "Agachamento sumô com barra", "po_sumo", {"sumo": true}],
    ["Glúteos", "Frog pump", "po_ponte", {"frog": true}],
    ["Panturrilha", "Panturrilha em pé na máquina", "pc_pant_pe", {}],
    ["Panturrilha", "Panturrilha sentado", "pc_pant_sentado", {}],
    ["Panturrilha", "Panturrilha no leg press", "pc_pant_legpress", {}],
    ["Panturrilha", "Panturrilha no Smith", "pc_pant_smith", {}],
    ["Panturrilha", "Panturrilha unilateral com halter", "pc_pant_degrau", {"uni": true, "halter": true}],
    ["Panturrilha", "Panturrilha no degrau", "pc_pant_degrau", {}],
    ["Panturrilha", "Panturrilha burrinho", "pc_burrinho", {}],
    ["Panturrilha", "Elevação de ponta de pé (tibial)", "pc_tibial", {}],
    ["Abdômen e core", "Abdominal supra no solo", "ab_supra", {}],
    ["Abdômen e core", "Abdominal infra (elevação de pernas)", "ab_infra", {}],
    ["Abdômen e core", "Abdominal na polia (crunch)", "ab_polia", {}],
    ["Abdômen e core", "Abdominal na máquina", "ab_maquina", {}],
    ["Abdômen e core", "Abdominal bicicleta", "ab_bicicleta", {}],
    ["Abdômen e core", "Abdominal canivete", "ab_canivete", {}],
    ["Abdômen e core", "Abdominal oblíquo", "ab_supra", {"obliquo": true}],
    ["Abdômen e core", "Abdominal declinado", "ab_declinado", {}],
    ["Abdômen e core", "Elevação de pernas na barra", "ab_barra", {}],
    ["Abdômen e core", "Elevação de joelhos na paralela", "ab_paralela", {}],
    ["Abdômen e core", "Roda abdominal", "ab_roda", {}],
    ["Abdômen e core", "Prancha frontal", "ab_prancha", {}],
    ["Abdômen e core", "Prancha lateral", "ab_prancha_lat", {}],
    ["Abdômen e core", "Prancha com toque no ombro", "ab_prancha_toque", {}],
    ["Abdômen e core", "Dead bug", "ab_deadbug", {}],
    ["Abdômen e core", "Bird dog", "ab_birddog", {}],
    ["Abdômen e core", "Pallof press", "ab_pallof", {}],
    ["Abdômen e core", "Lenhador na polia", "ab_lenhador", {}],
    ["Abdômen e core", "Russian twist", "ab_russian", {}],
    ["Abdômen e core", "Hollow hold", "ab_hollow", {}],
    ["Abdômen e core", "Mountain climber", "ab_mountain", {}],
    ["Abdômen e core", "Flexão lateral com halter", "ab_flexlat", {}],
    ["Cardio e funcional", "Esteira", "pc_esteira", {}],
    ["Cardio e funcional", "Bicicleta ergométrica", "pc_bike", {}],
    ["Cardio e funcional", "Elíptico", "pc_eliptico", {}],
    ["Cardio e funcional", "Remo ergômetro", "pc_remo", {}],
    ["Cardio e funcional", "Escada (stairmaster)", "pc_escada", {}],
    ["Cardio e funcional", "Pular corda", "pc_corda", {}],
    ["Cardio e funcional", "Burpee", "pc_burpee", {}],
    ["Cardio e funcional", "Polichinelo", "pc_polichinelo", {}],
    ["Cardio e funcional", "Farmer walk", "pc_farmer", {}],
    ["Cardio e funcional", "Battle rope", "pc_battle", {}],
    ["Cardio e funcional", "Kettlebell goblet squat", "pc_goblet", {}],
    ["Cardio e funcional", "Arremesso de medicine ball", "pc_arremesso", {}],
    /*CATALOGO-FIM*/
  ];

  // sinonimos aplicados no nome da ficha E no do catalogo (os dois lados falam a mesma lingua)
  var SINONIMOS = [
    [/\b(dumbbells?|db)\b/g, "halter"],
    [/\bbench( press)?\b/g, "supino"],
    [/\bvoador inverso\b/g, "crucifixo inverso maquina"],
    [/\bcrucifixo (na )?maquina\b/g, "voador"],
    [/\bpec+k? ?deck\b/g, "voador"],
    [/\bpuxada (alta|pela frente|na frente|frente)\b/g, "puxada frontal"],
    [/\b(pulley|cabo|cross over)\b/g, "polia"],
    [/\bhip thrust\b/g, "elevacao pelvica"],
    [/\b(rdl|romeno)\b/g, "terra romeno"],
    [/\b(afundo|lunges?)\b/g, "avanco"],
    [/\bmilitar\b/g, "barra em pe"],
    [/\bremada sentada\b/g, "remada baixa"],
    [/\bshoulder press\b/g, "desenvolvimento"],
    [/\bsquat\b/g, "agachamento"],
    [/\bdeadlift\b/g, "levantamento terra"],
    [/\bleg curl\b/g, "flexora"],
    [/\bleg extension\b/g, "extensora"],
    [/\babdomen\b/g, "abdominal"],
    [/\bplank\b/g, "prancha"],
    [/\b(calf|gemeos)\b/g, "panturrilha"],
    [/\b(pull ?ups?|chin ?ups?)\b/g, "barra fixa"],
    [/\bpull ?down\b/g, "pulldown"],
    [/\bpush ?ups?\b/g, "flexao braco"],
    [/\bdips?\b/g, "mergulho"],
    [/\bkickback\b/g, "coice"],
    [/\bhammer\b/g, "martelo"],
    [/\bt ?bar\b/g, "cavalinho"],
    [/\bleg 45\b/g, "leg press 45"],
    [/\bbike\b/g, "bicicleta"],
  ];
  var VAZIAS = { com: 1, de: 1, do: 1, da: 1, dos: 1, das: 1, no: 1, na: 1, nos: 1, nas: 1, em: 1, e: 1, o: 1, a: 1, os: 1, as: 1, pra: 1, para: 1, graus: 1 };

  function texto(nome) {
    return String(nome)
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .replace(/\d+\s*x\s*\d+/g, " ") // 4x10
      .replace(/\d+([.,]\d+)?\s*kg\b/g, " ") // 20 kg
      .replace(/[^a-z0-9]+/g, " ")
      .trim();
  }
  // "inclinado"/"inclinada" -> "inclin", "halteres"/"halter" -> "halter": plural fora e 6 letras
  function raizes(nome) {
    var s = texto(nome);
    for (var i = 0; i < SINONIMOS.length; i++) s = s.replace(SINONIMOS[i][0], SINONIMOS[i][1]);
    var out = [];
    s.split(" ").forEach(function (p) {
      if (!p || VAZIAS[p]) return;
      if (p.length > 3 && p.charAt(p.length - 1) === "s") p = p.slice(0, -1);
      p = p.slice(0, 6);
      if (out.indexOf(p) < 0) out.push(p);
    });
    return out;
  }

  var INDICE = CATALOGO.map(function (c) { return raizes(c[1]); });
  var POR_NOME = {};
  CATALOGO.forEach(function (c) { POR_NOME[c[1]] = c; });

  // melhor = cobre mais do que ele escreveu; empate: o nome exato ("Supino fechado" nao vira "Supino com pegada
  // fechada"), depois o que COMECA pelo mesmo movimento ("bicicleta" = ergometrica, nao abdominal bicicleta),
  // depois a ordem do catalogo (variacao mais comum primeiro: "Agachamento" = livre com barra).
  // A primeira palavra dele tem que estar no nome, e pelo menos 60% das palavras tem que bater.
  function tipo(nome) {
    if (typeof nome !== "string" || !nome.trim()) return null;
    var q = raizes(nome);
    if (!q.length) return null;
    var melhor = null, mCob = 0, mExa = 0, mCab = 0;
    for (var i = 0; i < INDICE.length; i++) {
      var c = INDICE[i];
      if (c.indexOf(q[0]) < 0) continue;
      var bate = 0;
      for (var k = 0; k < q.length; k++) if (c.indexOf(q[k]) >= 0) bate++;
      var cob = bate / q.length, exa = bate === c.length ? 1 : 0, cab = c[0] === q[0] ? 1 : 0;
      if (cob < 0.6) continue;
      if (cob > mCob || (cob === mCob && (exa > mExa || (exa === mExa && cab > mCab)))) {
        melhor = CATALOGO[i][1]; mCob = cob; mExa = exa; mCab = cab;
      }
    }
    return melhor;
  }

  function acha(nomeCatalogo) {
    return (nomeCatalogo && POR_NOME[nomeCatalogo]) || null;
  }

  return { tipo: tipo, acha: acha, lista: CATALOGO.map(function (c) { return c[1]; }), _raizes: raizes };
})();
if (typeof module !== "undefined" && module.exports) module.exports = Treino3DCatalogo;
