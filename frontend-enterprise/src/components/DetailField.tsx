import * as Source from '@staffdeck/business-ui/FormalDetailField';
import { FormalPrimitives } from '../business-ui/formal-primitives';
import type { ComponentProps } from 'react';
export * from '@staffdeck/business-ui/FormalDetailField';
export function DetailField(props: ComponentProps<typeof Source.DetailField>) { return <FormalPrimitives><Source.DetailField {...props} /></FormalPrimitives>; }
