import { create } from 'zustand';

export type PostColor = 'terracota' | 'verde' | 'mostaza' | 'taupe';

export type Post = {
  id: string;
  name: string;
  role: string;
  initial: string;
  color: PostColor;
  time: string;
  place: string;
  image: string;
  caption: string;
  tags: string[];
  likes: string;
  comments: number;
  shares: number;
  acceptsCommissions: boolean;
};

const INITIAL_POSTS: Post[] = [
  {
    id: '1',
    name: 'Luna Atelier',
    role: 'Ilustradora',
    initial: 'L',
    color: 'terracota',
    time: 'hace 15 min',
    place: 'San José',
    image: 'https://picsum.photos/seed/luna-atelier/800/900',
    caption:
      'Fragmentos de luz para días que necesitan un poco más de color. Esta serie salió de una tarde lluviosa en la que no tenía ganas de pintar nada en particular, solo de mezclar acuarelas hasta encontrar un tono que me gustara. Terminé haciendo seis bocetos y este fue el único que sobrevivió la noche.',
    tags: ['ilustracion', 'acuarela', 'arteCR'],
    likes: '1.3k',
    comments: 24,
    shares: 8,
    acceptsCommissions: true,
  },
  {
    id: '2',
    name: 'Mateo Ríos',
    role: 'Pintor',
    initial: 'M',
    color: 'verde',
    time: 'hace 2 h',
    place: 'Heredia',
    image: 'https://picsum.photos/seed/mateo-rios/800/900',
    caption:
      'Explorando texturas nuevas esta semana. Dejé el pincel plano de lado y volví a las espátulas, que llevaban meses guardadas. Hay algo en raspar la pintura en vez de extenderla que me obliga a pensar la composición de otra forma, menos prolija y más honesta.',
    tags: ['oleo', 'texturas'],
    likes: '842',
    comments: 12,
    shares: 3,
    acceptsCommissions: false,
  },
  {
    id: '3',
    name: 'Sofi Cerámica',
    role: 'Ceramista',
    initial: 'S',
    color: 'mostaza',
    time: 'hace 5 h',
    place: 'Cartago',
    image: 'https://picsum.photos/seed/sofi-ceramica/800/900',
    caption:
      'Nueva tanda saliendo del horno, todavía tibia. Esta vez probé un esmalte distinto, más mate, y el resultado me sorprendió para bien. Son catorce piezas en total, cada una con su propia mancha de ceniza que nunca sale igual dos veces.',
    tags: ['ceramica', 'hechoamano'],
    likes: '2.1k',
    comments: 47,
    shares: 15,
    acceptsCommissions: true,
  },
  {
    id: '4',
    name: 'Taller Norte',
    role: 'Artesanos',
    initial: 'T',
    color: 'taupe',
    time: 'hace 8 h',
    place: 'Alajuela',
    image: 'https://picsum.photos/seed/taller-norte/800/900',
    caption:
      'Trabajando el cuero para el pedido de esta semana. El tinte natural necesita por lo menos tres capas para agarrar bien el color, así que esto viene siendo un proceso lento que no se puede apurar. Vale la pena cuando ves el brillo final.',
    tags: ['cuero', 'talabarteria'],
    likes: '390',
    comments: 6,
    shares: 2,
    acceptsCommissions: false,
  },
  {
    id: '5',
    name: 'Vale Grabados',
    role: 'Grabadora',
    initial: 'V',
    color: 'terracota',
    time: 'hace 12 h',
    place: 'Grecia',
    image: 'https://picsum.photos/seed/vale-grabados/800/900',
    caption:
      'Primera tirada de la serie nueva, tinta todavía fresca. Son veinte ejemplares numerados, grabados a mano en linóleo, y cada uno lleva una pequeña variación porque el rodillo nunca reparte la tinta exactamente igual. Me gusta que ninguno sea idéntico al otro.',
    tags: ['grabado', 'serigrafia'],
    likes: '1.7k',
    comments: 31,
    shares: 9,
    acceptsCommissions: true,
  },
  {
    id: '6',
    name: 'Nico Escultor',
    role: 'Escultor',
    initial: 'N',
    color: 'verde',
    time: 'ayer',
    place: 'Puntarenas',
    image: 'https://picsum.photos/seed/nico-escultor/800/900',
    caption:
      'Piedra bruta convirtiéndose en algo con forma, de a poco. Llevo tres semanas con este bloque de mármol y todavía me falta pulir la base. Hay días en que el cincel no coopera y otros en que todo fluye solo, hoy fue de los buenos.',
    tags: ['escultura', 'piedra'],
    likes: '654',
    comments: 18,
    shares: 4,
    acceptsCommissions: false,
  },
  {
    id: '7',
    name: 'Cami Lentes',
    role: 'Fotógrafa',
    initial: 'C',
    color: 'mostaza',
    time: 'ayer',
    place: 'Escazú',
    image: 'https://picsum.photos/seed/cami-lentes/800/900',
    caption:
      'Rollo revelado de la sesión del fin de semana, todavía con olor a químico. Volví a usar película de 35mm después de mucho tiempo solo con digital y se siente distinto, más lento, más pensado. De treinta y seis tomas me quedo con estas cuatro.',
    tags: ['fotografia', 'analoga'],
    likes: '975',
    comments: 21,
    shares: 6,
    acceptsCommissions: true,
  },
  {
    id: '8',
    name: 'Diego Tinta',
    role: 'Tatuador',
    initial: 'D',
    color: 'taupe',
    time: 'hace 2 d',
    place: 'Liberia',
    image: 'https://picsum.photos/seed/diego-tinta/800/900',
    caption:
      'Diseño flash disponible para quien se anime primero. Lo dibujé pensando en líneas simples que envejezcan bien con los años, nada de detalles que se van a perder con el tiempo. Si te late, escribime y coordinamos la cita.',
    tags: ['tatuaje', 'lineart'],
    likes: '1.1k',
    comments: 38,
    shares: 11,
    acceptsCommissions: false,
  },
  {
    id: '9',
    name: 'Pau Murales',
    role: 'Muralista',
    initial: 'P',
    color: 'terracota',
    time: 'hace 2 d',
    place: 'Turrialba',
    image: 'https://picsum.photos/seed/pau-murales/800/900',
    caption:
      'Último día de andamio, la pared ya respira otro color. Fueron casi dos semanas de trabajo, entre el calor del mediodía y la gente que paraba a preguntar qué estaba pintando. Ver el mural terminado desde la otra cuadra fue la mejor parte de todo el proceso.',
    tags: ['mural', 'streetart', 'arteCR'],
    likes: '2.4k',
    comments: 52,
    shares: 19,
    acceptsCommissions: true,
  },
  {
    id: '10',
    name: 'Rita Telar',
    role: 'Tejedora',
    initial: 'R',
    color: 'verde',
    time: 'hace 3 d',
    place: 'Zarcero',
    image: 'https://picsum.photos/seed/rita-telar/800/900',
    caption:
      'Hilos teñidos con plantas del patio, cada tanda sale distinta. Esta vez usé cáscara de cebolla y hojas de aguacate, y el resultado fue un marrón cálido que no esperaba. Ya está montado en el telar, en unos días les muestro cómo va quedando la pieza.',
    tags: ['textil', 'telar'],
    likes: '703',
    comments: 14,
    shares: 5,
    acceptsCommissions: false,
  },
  {
    id: '11',
    name: 'Fabián Sarchí',
    role: 'Luthier',
    initial: 'F',
    color: 'mostaza',
    time: 'hace 1 sem',
    place: 'Sarchí',
    image: 'https://picsum.photos/seed/fabian-sarchi/800/900',
    caption:
      'Afinando la última guitarra de la tanda antes de entregarla. Esta la hice con cedro y laurel, una combinación que me enseñó mi papá y que todavía prefiero sobre cualquier madera importada. Suena cálida, como esperaba.',
    tags: ['luthier', 'madera', 'hechoamano'],
    likes: '1.5k',
    comments: 29,
    shares: 13,
    acceptsCommissions: true,
  },
];

type PostsState = {
  posts: Post[];
  addPost: (post: Omit<Post, 'id' | 'likes' | 'comments' | 'shares'>) => void;
};

// Mock de sesion, sin persistencia: el feed se resetea a INITIAL_POSTS al
// recargar la app. Cuando exista el backend, addPost se reemplaza por la
// mutacion real y esta store se puede borrar.
export const usePostsStore = create<PostsState>((set) => ({
  posts: INITIAL_POSTS,
  addPost: (post) =>
    set((state) => ({
      posts: [
        { ...post, id: `local-${Date.now()}`, likes: '0', comments: 0, shares: 0 },
        ...state.posts,
      ],
    })),
}));
