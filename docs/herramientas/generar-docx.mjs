// Genera la documentacion oficial en Word a partir del Markdown de docs/.
// Uso: npm run generar -- [entrada.md] [salida.docx]
// Cubre el subconjunto de Markdown que usa la documentacion: portada, titulos
// de nivel 2 a 4, parrafos con negrita y codigo, listas, tablas y separadores.

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
  Packer,
  PageBreak,
  PageNumber,
  Paragraph,
  ShadingType,
  Table,
  TableCell,
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
      return new TextRun({ ...base, text: parte.slice(1, -1), font: "Consolas", size: 19 });
    }
    return new TextRun({ ...base, text: parte });
  });
}

function celdas(linea) {
  return linea.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
}

// Ancho de cada columna proporcional al texto mas largo, con un minimo
function anchos(filas) {
  const columnas = filas[0].length;
  const largo = Array.from({ length: columnas }, (_, i) =>
    Math.max(...filas.map((f) => (f[i] ?? "").replace(/\*\*|`/g, "").length)),
  );
  const peso = largo.map((l) => Math.max(8, Math.min(l, 70)));
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
          children: fila.map(
            (texto, j) =>
              new TableCell({
                width: { size: columnas[j], type: WidthType.DXA },
                borders: bordes,
                shading: i === 0 ? { type: ShadingType.CLEAR, color: "auto", fill: PAPEL } : undefined,
                margins: { top: 60, bottom: 60, left: 100, right: 100 },
                children: [
                  new Paragraph({
                    spacing: { after: 0 },
                    children: tramos(texto, { size: 19, bold: i === 0 ? true : undefined }),
                  }),
                ],
              }),
          ),
        }),
    ),
  });
}

const salto = () => new Paragraph({ children: [new PageBreak()] });

function portada(lineas) {
  const bloque = [];
  for (const linea of lineas) {
    const t = linea.trim();
    if (!t) continue;
    if (t.startsWith("# ")) {
      bloque.push(
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 2400, after: 200 },
          children: [new TextRun({ text: t.slice(2), size: 72, bold: true, color: TERRACOTA })],
        }),
      );
    } else if (t.startsWith("**")) {
      bloque.push(
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 1200 },
          children: [new TextRun({ text: t.replace(/\*\*/g, ""), italics: true, size: 28, color: TINTA_SUAVE })],
        }),
      );
    } else {
      bloque.push(
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 160 },
          children: [new TextRun({ text: t, size: 24 })],
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
  for (let i = 0; i < lineas.length; i++) {
    const linea = lineas[i];
    const t = linea.trim();

    if (!/^\d+\.\s/.test(t) && !t.startsWith("- ")) enLista = false;
    if (!t) continue;

    if (t === "---") {
      bloque.push(salto());
    } else if (t.startsWith("#### ")) {
      bloque.push(new Paragraph({ heading: HeadingLevel.HEADING_3, children: tramos(t.slice(5)) }));
    } else if (t.startsWith("### ")) {
      bloque.push(new Paragraph({ heading: HeadingLevel.HEADING_2, children: tramos(t.slice(4)) }));
    } else if (t.startsWith("## ")) {
      bloque.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: tramos(t.slice(3)) }));
    } else if (t.startsWith("|")) {
      const filas = [];
      while (i < lineas.length && lineas[i].trim().startsWith("|")) {
        const fila = celdas(lineas[i]);
        if (!fila.every((c) => /^:?-+:?$/.test(c))) filas.push(fila);
        i++;
      }
      i--;
      bloque.push(tabla(filas));
      bloque.push(new Paragraph({ spacing: { after: 120 }, children: [] }));
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
        bloque.push(new Paragraph({ children: [new TextRun({ text: lineas[i], font: "Consolas", size: 18 })] }));
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

const documento = new Document({
  creator: "Brian José Zeledón Esquivel y Esteban Granados Sibaja",
  title: `${titulo}, documentación del proyecto`,
  styles: {
    default: { document: { run: { font: "Calibri", size: 22, color: TINTA } } },
    paragraphStyles: [
      {
        id: "Heading1",
        name: "Heading 1",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 36, bold: true, color: TERRACOTA },
        paragraph: { spacing: { before: 240, after: 200 }, outlineLevel: 0 },
      },
      {
        id: "Heading2",
        name: "Heading 2",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 28, bold: true, color: TINTA },
        paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1 },
      },
      {
        id: "Heading3",
        name: "Heading 3",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 24, bold: true, color: TERRACOTA },
        paragraph: { spacing: { before: 220, after: 100 }, outlineLevel: 2 },
      },
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
            style: { paragraph: { indent: { left: 540, hanging: 270 } } },
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
            style: { paragraph: { indent: { left: 540, hanging: 360 } } },
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
                new TextRun({ text: `${titulo}, ${entrega}    `, size: 16, color: TINTA_SUAVE }),
                new TextRun({ children: [PageNumber.CURRENT], size: 16, color: TINTA_SUAVE }),
              ],
            }),
          ],
        }),
        first: new Footer({ children: [] }),
      },
      children: [...portada(lineasPortada), salto(), ...cuerpo(lineasCuerpo)],
    },
  ],
});

mkdirSync(dirname(salida), { recursive: true });
writeFileSync(salida, await Packer.toBuffer(documento));
console.log(`Generado: ${salida}`);
