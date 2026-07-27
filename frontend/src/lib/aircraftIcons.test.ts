import { describe, expect, it } from 'vitest';
import {
  aircraftIconPolygon,
  classifyAircraftIcon,
} from './aircraftIcons';

describe('classifyAircraftIcon', () => {
  it('classifies helicopters', () => {
    expect(classifyAircraftIcon('EC35')).toBe('helicopter');
    expect(classifyAircraftIcon('R44')).toBe('helicopter');
    expect(classifyAircraftIcon(null, 'Airbus Helicopters H135')).toBe('helicopter');
  });

  it('classifies light GA / Cessna-class', () => {
    expect(classifyAircraftIcon('C172')).toBe('light_ga');
    expect(classifyAircraftIcon('SR22')).toBe('light_ga');
  });

  it('classifies turboprops', () => {
    expect(classifyAircraftIcon('DH8D')).toBe('turboprop');
    expect(classifyAircraftIcon('AT76')).toBe('turboprop');
  });

  it('classifies narrowbody jets as jet', () => {
    expect(classifyAircraftIcon('A320')).toBe('jet');
    expect(classifyAircraftIcon('B738')).toBe('jet');
  });

  it('classifies heavy widebodies', () => {
    expect(classifyAircraftIcon('B77W')).toBe('heavy');
    expect(classifyAircraftIcon('B789')).toBe('heavy');
  });

  it('classifies jumbos', () => {
    expect(classifyAircraftIcon('B744')).toBe('jumbo');
    expect(classifyAircraftIcon('A388')).toBe('jumbo');
  });

  it('defaults unknown types to jet', () => {
    expect(classifyAircraftIcon(undefined, undefined)).toBe('jet');
    expect(classifyAircraftIcon('XXXX')).toBe('jet');
  });
});

describe('aircraftIconPolygon', () => {
  it('returns different polygons for key families', () => {
    const heli = JSON.stringify(aircraftIconPolygon('EC35'));
    const cessna = JSON.stringify(aircraftIconPolygon('C172'));
    const a320 = JSON.stringify(aircraftIconPolygon('A320'));
    const jumbo = JSON.stringify(aircraftIconPolygon('B744'));

    expect(new Set([heli, cessna, a320, jumbo]).size).toBe(4);
  });
});
