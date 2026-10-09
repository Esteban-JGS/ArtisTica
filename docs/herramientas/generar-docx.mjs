// Genera la documentacion oficial en Word a partir del Markdown de docs/.
// Uso: npm run generar -- [entrada.md] [salida.docx]
// Cubre el subconjunto de Markdown que usa la documentacion: portada, titulos
// de nivel 2 a 4, parrafos con negrita y codigo, listas, tablas y separadores.
// "## Índice" se reemplaza por una tabla de contenido de Word; para llenarla
// con los numeros de pagina hay que correr despues actualizar-indice.ps1.

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  AlignmentType,
  BorderStyle,
  Document,
  Footer,
  HeadingLevel,
  LevelFormat,
  LineRuleType,
  Packer,
  PageBreak,
  PageNumber,
  Paragraph,
  ShadingType,
  Table,
  TableCell,
  TableOfContents,
  TableRow,
  TextRun,
  WidthType,
} from "docx";

const aqui = dirname(fileURLToPath(import.meta.url));
const entrada = resolve(process.argv[2] ?? resolve(aqui, "../ArtisTica_Documentacion_Oficial.md"));
const salida = resolve(process.argv[3] ?? resolve(aqui, "../entregas/ArtisTica_II_Avance.docx"));

// Paleta de la marca, tomada del Business Model Canvas
const TERRACOTA = "B85C38";
const TINTA = "2A221C";
const TINTA_SUAVE = "6B5D52";
const PAPEL = "F5EFE4";
const BORDE = "D9CDBA";

// Tipografia: Arial en todo el documento. Word mide en medios puntos
const FUENTE = "Arial";
const PT = (puntos) => puntos * 2;
const TAM_TEXTO = PT(12);
const TAM_TABLA = PT(10);
// Las tablas de hasta estas filas, encabezado incluido, se mantienen en una pagina
const FILAS_TABLA_JUNTA = 8;
const TAM_PIE = PT(9);
const INTERLINEADO = 276; // 1.15 lineas

// Carta con margenes de una pulgada: 12240 menos 2 por 1440
const ANCHO_UTIL = 9360;

// Texto en linea: **negrita** y `codigo`
function tramos(texto, base = {}) {
  const partes = texto.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean);
  return partes.map((parte) => {
    if (parte.startsWith("**") && parte.endsWith("**")) {
      return new TextRun({ ...base, text: parte.slice(2, -2), bold: true });
    }
    if (parte.startsWith("`") && parte.endsWith("`")) {
      return new TextRun({ ...base, text: parte.slice(1, -1), font: "Consolas" });
    }
    return new TextRun({ ...base, text: parte });
  });
}

function celdas(linea) {
  return linea.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
}

// Ancho de cada columna proporcional al texto mas largo, sin partir palabras
function anchos(filas) {
  const columnas = filas[0].length;
  const limpio = (f, i) => (f[i] ?? "").replace(/\*\*|`/g, "");
  const largo = Array.from({ length: columnas }, (_, i) => Math.max(...filas.map((f) => limpio(f, i).length)));
  const palabra = Array.from({ length: columnas }, (_, i) =>
    Math.max(...filas.flatMap((f) => limpio(f, i).split(/\s+/).map((p) => p.length))),
  );
  const peso = largo.map((l, i) => Math.max(palabra[i] + 4, Math.min(l, 50)));
  const total = peso.reduce((a, b) => a + b, 0);
  const res = peso.map((p) => Math.floor((p / total) * ANCHO_UTIL));
  res[res.length - 1] += ANCHO_UTIL - res.reduce((a, b) => a + b, 0);
  return res;
}

function tabla(filas) {
  const columnas = anchos(filas);
  const borde = { style: BorderStyle.SINGLE, size: 4, color: BORDE };
  const bordes = { top: borde, bottom: borde, left: borde, right: borde };
  return new Table({
    width: { size: ANCHO_UTIL, type: WidthType.DXA },
    columnWidths: columnas,
    rows: filas.map(
      (fila, i) =>
        new TableRow({
          tableHeader: i === 0,
          cantSplit: true,
          children: fila.map(
            (texto, j) =>
              new TableCell({
                width: { size: columnas[j], type: WidthType.DXA },
                borders: bordes,
                shading: i === 0 ? { type: ShadingType.CLEAR, color: "auto", fill: PAPEL } : undefined,
                margins: { top: 60, bottom: 60, left: 100, right: 100 },
                children: [
                  new Paragraph({
                    spacing: { after: 0, line: 240 },
                    // Una tabla corta no se parte entre paginas; una larga si, para no dejar huecos
                    keepNext: filas.length <= FILAS_TABLA_JUNTA && i < filas.length - 1,
                    children: tramos(texto, { size: TAM_TABLA, bold: i === 0 ? true : undefined }),
                  }),
                ],
              }),
          ),
        }),
    ),
  });
}

const salto = () => new Paragraph({ children: [new PageBreak()] });

// Titulo de nivel 1 que no entra al indice: Control de versiones e Índice
const tituloSinIndice = (texto, pageBreakBefore) =>
  new Paragraph({
    pageBreakBefore,
    spacing: { after: 160 },
    children: [new TextRun({ text: texto, size: PT(16), bold: true, color: TERRACOTA })],
  });

function portada(lineas) {
  const bloque = [];
  for (const linea of lineas) {
    const t = linea.trim();
    if (!t) continue;
    if (t.startsWith("# ")) {
      bloque.push(
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 2800, after: 200 },
          children: [new TextRun({ text: t.slice(2), size: PT(32), bold: true, color: TERRACOTA })],
        }),
      );
    } else if (t.startsWith("**")) {
      bloque.push(
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 1600 },
          children: [new TextRun({ text: t.replace(/\*\*/g, ""), italics: true, size: PT(14), color: TINTA_SUAVE })],
        }),
      );
    } else {
      bloque.push(
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 120 },
          children: [new TextRun({ text: t })],
        }),
      );
    }
  }
  return bloque;
}

function cuerpo(lineas) {
  const bloque = [];
  let listaNumerada = 0;
  let enLista = false;
  // "---" abre pagina nueva. Se aplica como salto antes del titulo siguiente y no
  // como parrafo propio, que deja una pagina en blanco si cae justo al final de otra
  let nuevaPagina = true;
  const tomarSalto = () => {
    const s = nuevaPagina;
    nuevaPagina = false;
    return s;
  };
  for (let i = 0; i < lineas.length; i++) {
    const linea = lineas[i];
    const t = linea.trim();

    if (!/^\d+\.\s/.test(t) && !t.startsWith("- ")) enLista = false;
    if (!t) continue;
    if (t !== "---" && !t.startsWith("## ") && tomarSalto()) bloque.push(salto());

    if (t === "---") {
      nuevaPagina = true;
    } else if (t === "## Índice") {
      // El indice escrito a mano en el Markdown se reemplaza por el de Word
      bloque.push(tituloSinIndice("Índice", tomarSalto()));
      bloque.push(new TableOfContents("Índice", { hyperlink: true, headingStyleRange: "1-2" }));
      while (i + 1 < lineas.length && lineas[i + 1].trim() !== "---") i++;
    } else if (t.startsWith("#### ")) {
      bloque.push(new Paragraph({ heading: HeadingLevel.HEADING_3, children: tramos(t.slice(5)) }));
    } else if (t.startsWith("### ")) {
      bloque.push(new Paragraph({ heading: HeadingLevel.HEADING_2, children: tramos(t.slice(4)) }));
    } else if (t.startsWith("## ")) {
      // Solo las secciones numeradas entran al indice
      const texto = t.slice(3);
      const pageBreakBefore = tomarSalto();
      bloque.push(
        /^\d/.test(texto)
          ? new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore, children: tramos(texto) })
          : tituloSinIndice(texto, pageBreakBefore),
      );
    } else if (t.startsWith("|")) {
      const filas = [];
      while (i < lineas.length && lineas[i].trim().startsWith("|")) {
        const fila = celdas(lineas[i]);
        if (!fila.every((c) => /^:?-+:?$/.test(c))) filas.push(fila);
        i++;
      }
      i--;
      bloque.push(tabla(filas));
      bloque.push(new Paragraph({ spacing: { before: 0, after: 0, line: 200, lineRule: LineRuleType.EXACT }, children: [] }));
    } else if (t.startsWith("- ")) {
      bloque.push(new Paragraph({ numbering: { reference: "vinetas", level: 0 }, children: tramos(t.slice(2)) }));
    } else if (/^\d+\.\s/.test(t)) {
      // Cada lista numerada reinicia su cuenta
      if (!enLista) listaNumerada++;
      enLista = true;
      bloque.push(
        new Paragraph({
          numbering: { reference: "numeros", level: 0, instance: listaNumerada },
          children: tramos(t.replace(/^\d+\.\s/, "")),
        }),
      );
    } else if (t.startsWith("```")) {
      i++;
      while (i < lineas.length && !lineas[i].trim().startsWith("```")) {
        bloque.push(new Paragraph({ children: [new TextRun({ text: lineas[i], font: "Consolas", size: TAM_TABLA })] }));
        i++;
      }
    } else {
      bloque.push(new Paragraph({ children: tramos(t) }));
    }
  }
  return bloque;
}

const texto = readFileSync(entrada, "utf-8").replace(/\r\n/g, "\n");
const lineas = texto.split("\n");
const fin = lineas.findIndex((l) => l.trim() === "---");
const lineasPortada = lineas.slice(0, fin);
const lineasCuerpo = lineas.slice(fin + 1);

const titulo = (lineasPortada.find((l) => l.startsWith("# ")) ?? "# ArtisTica").slice(2);
const entrega = lineasPortada.map((l) => l.trim()).find((l) => /avance/i.test(l)) ?? "";

// Titulos: 16, 14 y 12 puntos, siempre pegados al parrafo que sigue
const estiloTitulo = (id, nivel, puntos, color, antes, despues) => ({
  id,
  name: id.replace(/(\d)/, " $1"),
  basedOn: "Normal",
  next: "Normal",
  quickFormat: true,
  run: { font: FUENTE, size: PT(puntos), bold: true, color },
  paragraph: { spacing: { before: antes, after: despues, line: 240 }, keepNext: true, outlineLevel: nivel },
});

const estiloIndice = (id, sangria, negrita) => ({
  id,
  name: id.replace(/(\d)/, " $1"),
  basedOn: "Normal",
  next: "Normal",
  run: { font: FUENTE, size: TAM_TEXTO, bold: negrita },
  paragraph: { spacing: { before: negrita ? 60 : 0, after: 20, line: 240 }, indent: { left: sangria } },
});

const documento = new Document({
  creator: "Brian José Zeledón Esquivel y Esteban Granados Sibaja",
  title: `${titulo}, documentación del proyecto`,
  features: { updateFields: true },
  styles: {
    default: {
      document: {
        run: { font: FUENTE, size: TAM_TEXTO, color: TINTA },
        paragraph: { spacing: { after: 160, line: INTERLINEADO } },
      },
    },
    paragraphStyles: [
      estiloTitulo("Heading1", 0, 16, TERRACOTA, 0, 240),
      estiloTitulo("Heading2", 1, 14, TINTA, 320, 120),
      estiloTitulo("Heading3", 2, 12, TERRACOTA, 200, 80),
      estiloIndice("TOC1", 0, true),
      estiloIndice("TOC2", 360, false),
    ],
  },
  numbering: {
    config: [
      {
        reference: "vinetas",
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: "•",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 540, hanging: 270 }, spacing: { after: 80 } } },
          },
        ],
      },
      {
        reference: "numeros",
        levels: [
          {
            level: 0,
            format: LevelFormat.DECIMAL,
            text: "%1.",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 540, hanging: 360 }, spacing: { after: 80 } } },
          },
        ],
      },
    ],
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 },
        },
        titlePage: true,
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              alignment: AlignmentType.RIGHT,
              children: [
                new TextRun({ text: `${titulo}, ${entrega}    `, size: TAM_PIE, color: TINTA_SUAVE }),
                new TextRun({ children: [PageNumber.CURRENT], size: TAM_PIE, color: TINTA_SUAVE }),
              ],
            }),
          ],
        }),
        first: new Footer({ children: [] }),
      },
      children: [...portada(lineasPortada), ...cuerpo(lineasCuerpo)],
    },
  ],
});

mkdirSync(dirname(salida), { recursive: true });
writeFileSync(salida, await Packer.toBuffer(documento));
console.log(`Generado: ${salida}`);
