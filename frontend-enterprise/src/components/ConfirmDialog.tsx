import * as Source from '@staffdeck/business-ui/FormalConfirmDialog';
import { FormalPrimitives } from '../business-ui/formal-primitives';
import type { ComponentProps } from 'react';
export * from '@staffdeck/business-ui/FormalConfirmDialog';
export function ConfirmDialog(props: ComponentProps<typeof Source.ConfirmDialog>) { return <FormalPrimitives><Source.ConfirmDialog {...props} /></FormalPrimitives>; }
