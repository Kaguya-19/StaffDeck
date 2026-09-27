import * as Source from '@staffdeck/business-ui/FormalPaginator';
import { FormalPrimitives } from '../business-ui/formal-primitives';
import type { ComponentProps } from 'react';
export * from '@staffdeck/business-ui/FormalPaginator';
export function Paginator(props: ComponentProps<typeof Source.Paginator>) { return <FormalPrimitives><Source.Paginator {...props} /></FormalPrimitives>; }
