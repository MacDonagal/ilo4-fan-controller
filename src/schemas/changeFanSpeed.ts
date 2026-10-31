import * as yup from "yup";

/**
 * - "lock": fans are pinned to the given speed, iLO thermal regulation is DISABLED.
 * - "min":  the given speed is only a floor, iLO can still ramp fans up when a
 *           component (CPU, Smart Array controller, ...) gets hot. Safer.
 */
export const FAN_MODES = ["lock", "min"] as const;
export type FanMode = (typeof FAN_MODES)[number];

export const changeFanSpeedSchema = yup.object().shape({
    fans: yup.array().of(yup.number().min(10).max(100).required()).required(),
    mode: yup.mixed<FanMode>().oneOf([...FAN_MODES]).default("lock"),
});

export type ChangeFanSpeedInput = yup.InferType<typeof changeFanSpeedSchema>;
