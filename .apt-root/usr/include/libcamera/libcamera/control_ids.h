/* SPDX-License-Identifier: LGPL-2.1-or-later */
/*
 * Copyright (C) 2019, Google Inc.
 *
 * control_ids.h - Control ID list
 *
 * This file is auto-generated. Do not edit.
 */

#ifndef __LIBCAMERA_CONTROL_IDS_H__
#define __LIBCAMERA_CONTROL_IDS_H__

#include <stdint.h>

#include <libcamera/controls.h>

namespace libcamera {

namespace controls {

enum {
	AE_ENABLE = 1,
	AE_LOCKED = 2,
	AE_METERING_MODE = 3,
	AE_CONSTRAINT_MODE = 4,
	AE_EXPOSURE_MODE = 5,
	EXPOSURE_VALUE = 6,
	EXPOSURE_TIME = 7,
	ANALOGUE_GAIN = 8,
	BRIGHTNESS = 9,
	CONTRAST = 10,
	LUX = 11,
	AWB_ENABLE = 12,
	AWB_MODE = 13,
	COLOUR_GAINS = 14,
	COLOUR_TEMPERATURE = 15,
	SATURATION = 16,
	SENSOR_BLACK_LEVELS = 17,
	SHARPNESS = 18,
};

extern const Control<bool> AeEnable;
extern const Control<bool> AeLocked;
enum AeMeteringModeValues {
	MeteringCentreWeighted = 0,
	MeteringSpot = 1,
	MeteringMatrix = 2,
	MeteringCustom = 3,
	MeteringModeMax = 3,
};
extern const Control<int32_t> AeMeteringMode;
enum AeConstraintModeValues {
	ConstraintNormal = 0,
	ConstraintHighlight = 1,
	ConstraintShadows = 2,
	ConstraintCustom = 3,
	ConstraintModeMax = 3,
};
extern const Control<int32_t> AeConstraintMode;
enum AeExposureModeValues {
	ExposureNormal = 0,
	ExposureShort = 1,
	ExposureLong = 2,
	ExposureCustom = 3,
	ExposureModeMax = 3,
};
extern const Control<int32_t> AeExposureMode;
extern const Control<float> ExposureValue;
extern const Control<int32_t> ExposureTime;
extern const Control<float> AnalogueGain;
extern const Control<float> Brightness;
extern const Control<float> Contrast;
extern const Control<float> Lux;
extern const Control<bool> AwbEnable;
enum AwbModeValues {
	AwbAuto = 0,
	AwbIncandescent = 1,
	AwbTungsten = 2,
	AwbFluorescent = 3,
	AwbIndoor = 4,
	AwbDaylight = 5,
	AwbCloudy = 6,
	AwbCustom = 7,
	AwbModeMax = 7,
};
extern const Control<int32_t> AwbMode;
extern const Control<Span<const float>> ColourGains;
extern const Control<int32_t> ColourTemperature;
extern const Control<float> Saturation;
extern const Control<Span<const int32_t>> SensorBlackLevels;
extern const Control<float> Sharpness;

extern const ControlIdMap controls;

} /* namespace controls */

} /* namespace libcamera */

#endif /* __LIBCAMERA_CONTROL_IDS_H__ */
