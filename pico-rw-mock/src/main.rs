#![no_main]
#![no_std]

use rp_pico::hal;
use hal::pac;

use panic_halt as _;

use embedded_hal::delay::DelayNs;
use embedded_hal::digital::OutputPin;
use embedded_hal::pwm::SetDutyCycle;
use embedded_hal_0_2::digital::v2::InputPin;

use defmt_rtt as _;

// USB HID
use hal::usb::UsbBus;
use usb_device::{class_prelude::*, prelude::*};
use usbd_hid::descriptor::generator_prelude::*;
use usbd_hid::hid_class::{
    HIDClass, HidClassSettings, HidCountryCode, HidProtocol, HidSubClass, ProtocolModeConfig,
};
use zerocopy::{FromBytes, Immutable, KnownLayout};

/// USB bus allocator (needs static lifetime)
static mut USB_BUS: Option<UsbBusAllocator<UsbBus>> = None;

/// HID Report descriptor for RW speed control
/// Output: speed_normalized (int16_t, little-endian)
/// Range: -32767 = -100%, 0 = stop, +32767 = +100%
#[gen_hid_descriptor(
    (collection = APPLICATION, usage_page = VENDOR_DEFINED_START, usage = 0x01) = {
        speed_normalized_low=output;
        speed_normalized_high=output;
    }
)]
struct RWSpeedReport {
    speed_normalized_low: u8,
    speed_normalized_high: u8,
}

/// Output report from host (normalized speed)
#[derive(FromBytes, KnownLayout, Immutable)]
#[repr(C)]
struct OutputReport {
    speed_normalized: i16,  // Normalized speed: -32767 to +32767 (-100% to +100%)
}

/// Motor speed state
#[derive(Clone, Copy)]
struct MotorSpeed {
    speed_normalized: i16,  // Normalized speed (-32767 to +32767)
}

impl MotorSpeed {
    fn to_duty_and_direction(&self) -> (u8, bool) {
        // Convert normalized speed (-32767 to +32767) to duty cycle (0-100%)
        // -32767 -> 100% reverse
        // 0 -> 0% (stop)
        // +32767 -> 100% forward

        let abs_speed = self.speed_normalized.abs();
        let is_forward = self.speed_normalized >= 0;

        // Scale: 32767 -> 100% duty
        // Use min duty of 40% when speed > 0
        let duty = if abs_speed == 0 {
            0
        } else {
            let scaled = (abs_speed as u32 * 100 / 32767).min(100) as u8;
            scaled.max(MIN_DUTY)
        };

        (duty, is_forward)
    }
}

/// Kickstart parameters
const KICKSTART_DUTY: u8 = 100;
const KICKSTART_MS: u32 = 150;
const MIN_DUTY: u8 = 40;

/// Axis identification for multi-Pico setup
#[derive(Debug, Clone, Copy, defmt::Format)]
enum Axis {
    X,
    Y,
    Z,
}

#[hal::entry]
fn main() -> ! {
    let mut pac = pac::Peripherals::take().unwrap();
    let mut watchdog = hal::Watchdog::new(pac.WATCHDOG);

    let clocks = hal::clocks::init_clocks_and_plls(
        rp_pico::XOSC_CRYSTAL_FREQ,
        pac.XOSC,
        pac.CLOCKS,
        pac.PLL_SYS,
        pac.PLL_USB,
        &mut pac.RESETS,
        &mut watchdog,
    )
    .unwrap();

    let mut timer = hal::timer::Timer::new(pac.TIMER, &mut pac.RESETS, &clocks);
    let sio = hal::Sio::new(pac.SIO);
    let pins = hal::gpio::Pins::new(
        pac.IO_BANK0,
        pac.PADS_BANK0,
        sio.gpio_bank0,
        &mut pac.RESETS,
    );

    // Detect axis from GPIO0 and GPIO1
    // Read GPIO pins with pull-up (LOW=0, HIGH=1)
    let id0 = pins.gpio0.into_pull_up_input();
    let id1 = pins.gpio1.into_pull_up_input();
    let bit0 = if id0.is_low().unwrap() { 0 } else { 1 };
    let bit1 = if id1.is_low().unwrap() { 0 } else { 1 };
    let axis_id = (bit1 << 1) | bit0;

    let axis = match axis_id {
        0b11 => Axis::X,  // Both HIGH (floating) → X-axis
        0b10 => Axis::Y,  // GPIO0=LOW, GPIO1=HIGH → Y-axis
        0b01 => Axis::Z,  // GPIO0=HIGH, GPIO1=LOW → Z-axis
        0b00 => panic!("Invalid axis ID: both GPIO0 and GPIO1 are LOW"),
        _ => unreachable!(),
    };

    let serial = match axis {
        Axis::X => "RW-X",
        Axis::Y => "RW-Y",
        Axis::Z => "RW-Z",
    };
    defmt::println!("Detected axis: {}, Serial: {}", axis, serial);

    // nSLEEP pin: set HIGH to enable motor driver
    let mut motor_sleep = pins.gpio18.into_push_pull_output();
    motor_sleep.set_high().unwrap();

    // Configure PWM slice 0
    // Target: ~10kHz PWM frequency
    // freq = 125MHz / (divider * TOP) = 125MHz / (5 * 2500) = 10kHz
    let mut pwm_slices = hal::pwm::Slices::new(pac.PWM, &mut pac.RESETS);
    let pwm0 = &mut pwm_slices.pwm0;
    pwm0.set_top(2500);
    pwm0.set_div_int(5u8);
    pwm0.enable();

    // AIN1: GPIO16 (PWM0 channel A)
    let ain1 = &mut pwm0.channel_a;
    ain1.output_to(pins.gpio16);

    // AIN2: GPIO17 (PWM0 channel B)
    let ain2 = &mut pwm0.channel_b;
    ain2.output_to(pins.gpio17);

    // Set up USB HID
    let usb_bus: &'static _ = unsafe {
        USB_BUS = Some(UsbBusAllocator::new(UsbBus::new(
            pac.USBCTRL_REGS,
            pac.USBCTRL_DPRAM,
            clocks.usb_clock,
            true,
            &mut pac.RESETS,
        )));
        USB_BUS.as_ref().unwrap()
    };

    let mut hid = HIDClass::new_with_settings(
        usb_bus,
        RWSpeedReport::desc(),
        10, // poll interval ms
        HidClassSettings {
            subclass: HidSubClass::NoSubClass,
            protocol: HidProtocol::Generic,
            config: ProtocolModeConfig::ForceReport,
            locale: HidCountryCode::NotSupported,
        },
    );

    let mut usb_dev = UsbDeviceBuilder::new(usb_bus, UsbVidPid(0x2E8A, 0x0B33))
        .strings(&[StringDescriptors::default()
            .manufacturer("sksat")
            .product("Reaction Wheel Visualizer")
            .serial_number(serial)])
        .unwrap()
        .max_packet_size_0(64)
        .unwrap()
        .build();

    defmt::println!("Reaction Wheel Visualizer Started (HID)");

    let mut current_speed = MotorSpeed { speed_normalized: 0 };
    let mut last_speed = current_speed;
    let mut usb_buf = [0u8; 64];

    // Stop motor initially
    ain1.set_duty_cycle_fully_off().unwrap();
    ain2.set_duty_cycle_fully_off().unwrap();

    loop {
        // Poll USB
        usb_dev.poll(&mut [&mut hid]);

        // Read output report from host
        if let Ok(len) = hid.pull_raw_output(&mut usb_buf) {
            if let Some(report) = OutputReport::ref_from_bytes(&usb_buf[..len]).ok() {
                current_speed.speed_normalized = report.speed_normalized;
                let percentage = (current_speed.speed_normalized as i32 * 100 / 32767) as i16;
                defmt::println!("HID recv: speed={}% ({})", percentage, current_speed.speed_normalized);

                // Apply motor command if speed changed
                if current_speed.speed_normalized != last_speed.speed_normalized {
                    apply_motor_speed(
                        last_speed,
                        current_speed,
                        ain1,
                        ain2,
                        &mut timer,
                    );
                    last_speed = current_speed;
                }
            }
        }
    }
}

/// Apply motor speed with kickstart logic
fn apply_motor_speed<A, B, T>(
    last: MotorSpeed,
    current: MotorSpeed,
    ain1: &mut A,
    ain2: &mut B,
    timer: &mut T,
)
where
    A: SetDutyCycle,
    B: SetDutyCycle,
    T: DelayNs,
{
    let (duty, is_forward) = current.to_duty_and_direction();
    let (last_duty, last_forward) = last.to_duty_and_direction();

    // Check if kickstart needed (direction change or start from stop)
    let needs_kickstart =
        (last_duty == 0 && duty > 0) ||  // Starting from stop
        (last_forward != is_forward && duty > 0);  // Direction change

    if duty == 0 {
        // Stop motor
        defmt::println!("Motor: STOP");
        let _ = ain1.set_duty_cycle_fully_off();
        let _ = ain2.set_duty_cycle_fully_off();
    } else if is_forward {
        if needs_kickstart {
            defmt::println!("Motor: FWD Kickstart -> {}%", duty);
            let _ = ain2.set_duty_cycle_fully_off();
            let _ = ain1.set_duty_cycle_percent(KICKSTART_DUTY);
            timer.delay_ms(KICKSTART_MS);
        }
        defmt::println!("Motor: FWD {}%", duty);
        let _ = ain2.set_duty_cycle_fully_off();
        let _ = ain1.set_duty_cycle_percent(duty);
    } else {
        if needs_kickstart {
            defmt::println!("Motor: REV Kickstart -> {}%", duty);
            let _ = ain1.set_duty_cycle_fully_off();
            let _ = ain2.set_duty_cycle_percent(KICKSTART_DUTY);
            timer.delay_ms(KICKSTART_MS);
        }
        defmt::println!("Motor: REV {}%", duty);
        let _ = ain1.set_duty_cycle_fully_off();
        let _ = ain2.set_duty_cycle_percent(duty);
    }
}
