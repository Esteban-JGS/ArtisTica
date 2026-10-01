import { makeMutable } from 'react-native-reanimated';

// A module-level (not per-component) shared value: scrolling the feed
// in home.tsx drives it, and the floating TabBar reads it, without
// prop drilling or context re-renders. 1 = shown, 0 = hidden off-screen.
export const navBarVisibility = makeMutable(1);
