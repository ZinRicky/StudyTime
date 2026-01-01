import os
from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd

# importing the csv in which to record study sessions
# subjects = list of subjects to study
data_file = "StudyTime.csv"
if os.path.exists(data_file):
    df = pd.read_csv(data_file)
    subjects = df["Subject"].fillna("NaN").unique().tolist()
else:
    subjects = []


def clear_screen():
    """
    clear the screen - Windows, Linux and MacOS
    """
    os.system("cls" if os.name == "nt" else "clear")


def select_subject(subjects):
    """
    functions that allows the user to select which subject to study
    """

    print("What subject are you studying?")
    for i, subj in enumerate(subjects, start=1):
        print(f"{i}. {subj}")
    print(f"{len(subjects)+1}. Add a new subject")

    choice = int(input("Select a number: "))
    if choice == len(subjects) + 1:
        new_subject = input("Enter new subject name: ").strip()
        subjects.append(new_subject)
        print(f"Added new subject: {new_subject}")
        return new_subject
    elif 1 <= choice <= len(subjects):
        return subjects[choice - 1]
    else:
        print("Invalid choice.")
        return select_subject(subjects)


def format_time(time):
    """
    prints time when given in seconds
    """
    # ensures that time is an integer
    time = time if type(time) == int else int(time)
    if time >= 3600:
        hours = int(time // 3600)
        rem_seconds = time % 3600
        min = int(rem_seconds // 60)
        sec = int(rem_seconds % 60)
        return f"{hours} h {min} min {sec} sec"
    else:
        min = int(time // 60)
        sec = int(time % 60)
        return f"{min} min {sec} sec"


def start_stopwatch():
    """
    Function that allows to keep track of time
    """
    print("Stopwatch started!")
    print("Commands:")
    print("  [c]  check elapsed time")
    print("  [s]  stop and save session")

    # take the initial time as a date, so even if the program temporary stops
    # running then we can take the true time spent. Moreover we can return
    # this time for some statistics
    start_time = datetime.now()

    while True:
        # this allows to check the time passed until now in this session
        # or to stop the stopwatch
        cmd = input("Enter command (c/s): ").strip().lower()

        if cmd == "c":
            end_time = datetime.now()
            elapsed_seconds = (end_time - start_time).total_seconds()
            print(f"You've studied for {format_time(elapsed_seconds)}\n")

        elif cmd == "s":
            end_time = datetime.now()
            elapsed_seconds = (end_time - start_time).total_seconds()
            print(f"You've studied for {format_time(elapsed_seconds)}\n")
            return elapsed_seconds, start_time

        else:
            print("Invalid command. Use c/s.\n")


def log_study_time(subject, seconds, start_time):
    """
    register the time of the session in the csv file
    """
    # date (first column)
    today = datetime.now().strftime("%Y-%m-%d")

    # time at which we have started the session
    start_time_str = start_time.strftime("%H:%M")
    # Load existing CSV or create a new one
    if os.path.exists(data_file):
        df = pd.read_csv(data_file)
    else:
        df = pd.DataFrame(columns=["Date", "Subject", "Seconds", "Start Time"])

    # Create the new row for this session
    new_row = {
        "Date": today,
        "Subject": subject,
        "Seconds": seconds,
        "Start Time": start_time_str,
    }

    # Append the row
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    # Save
    df.to_csv(data_file, index=False)

    print(f"You have just studied {subject} for {format_time(seconds)}.\n")


def weekly_df(df, past_weeks=1):
    """
    Return daily study time for a rolling week.

    past_weeks=1 → last 7 days (today included)
    past_weeks=2 → 7 days before last week
    """

    df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()

    today = pd.Timestamp.today().normalize()

    # Define rolling window
    end_day = today - pd.Timedelta(days=7 * (past_weeks - 1))
    start_day = end_day - pd.Timedelta(days=6)

    # Filter
    df_selected = df[(df["Date"] >= start_day) & (df["Date"] <= end_day)]

    # Aggregate per day
    df_daily = df_selected.groupby("Date")["Seconds"].sum()

    # Full 7-day range (forces missing days)
    full_range = pd.date_range(start=start_day, end=end_day, freq="D")

    df_daily_full = df_daily.reindex(full_range, fill_value=0)

    return df_daily_full



def show_statistics():
    """
    Prints some statistics related to previous study sessions
    """
    if not os.path.exists(data_file):
        print("No study data yet.")
        return

    df = pd.read_csv(data_file)

    print("\n====📊 Study Statistics 📊====")

    # Total minutes per subject
    print("\nTotal minutes per subject:")
    df_subj = df.groupby("Subject")["Seconds"].sum()
    print(df_subj.apply(format_time))

    # Daily totals of last last week
    df_daily_full = weekly_df(df, 1)
    print("\n Total minutes studied per day in the last week")
    print(df_daily_full.apply(format_time))

    # Overall total study time of the past week
    total_all = df_daily_full.sum()
    print(f"\nOverall study time in the last week: {format_time(total_all)}\n")

    # Comparison with the previous week
    df_daily_full_prev_week = weekly_df(df, 2)
    #print("\n Total minutes studied per day in the previous week")
    #print(df_daily_full_prev_week.apply(format_time))

    total_all_prev_week = df_daily_full_prev_week.sum()
    print(f"\nOverall study time in the previous week: {format_time(total_all_prev_week)}\n")

def show_plots():
    """
    Shows a pie chart with the different subjects and
    a bar plot with the study time of the last 7 days
    """

    if not os.path.exists(data_file):
        print("No study data yet.")
        return

    df = pd.read_csv(data_file)
    df_subj = df.groupby("Subject")["Seconds"].sum()

    # plotting the pie chart
    plt.figure(figsize=(6, 6))

    # Custom autopct that prints hours instead of percentage
    def show_hours(pct, all_vals):
        total = sum(all_vals)
        hours = pct * total / 100
        return f"{hours:.1f} h"

    df_subj.plot(
        kind="pie", autopct=lambda pct: show_hours(pct, df_subj / 3600), ylabel=""
    )
    plt.title("Study Time Distribution by Subject")
    plt.ylabel("")
    plt.show()

    # computing values for histogram of study time
    # of the last week
    df_daily_full = weekly_df(df, 1)

    # Convert seconds → hours
    df_daily_hours = df_daily_full / 3600
    # Mean study time (in hours)
    mean_hours = df_daily_hours.mean()

    # --- HISTOGRAM / BAR CHART ---
    plt.style.use("seaborn-v0_8")
    plt.figure(figsize=(10, 5))
    color = plt.cm.Blues(0.6)
    plt.bar(df_daily_hours.index, df_daily_hours.values, color=color)

    # Add dashed horizontal mean line
    plt.axhline(mean_hours, color="black", linestyle="--", linewidth=1.5)

    # adding a grid
    plt.grid(axis="y", linestyle="--", alpha=0.4)

    plt.title("Study Time in the Last Week", fontsize=16, pad=20)
    plt.xlabel("Date", fontsize=12)
    plt.ylabel("Hours Studied", fontsize=12)
    plt.xticks(rotation=45)
    plt.tight_layout()

    plt.show()


def add_time():
    pass


# ---------- MAIN PROGRAM ----------


def main():

    clear_screen()
    while True:
        print("\n===== STUDY TRACKER =====")
        print("1. Start a study session")
        print("2. View statistics")
        print("3. View visual statistics")
        print("4. Exit")

        choice = input("Choose an option: ").strip()

        if choice == "1":
            subject = select_subject(subjects)
            elapsed_seconds, start_time = start_stopwatch()
            log_study_time(subject, elapsed_seconds, start_time)
        elif choice == "2":
            show_statistics()
        elif choice == "3":
            show_plots()
        elif choice == "4":
            print("Goodbye! 👋")
            break
        else:
            print("Invalid choice. Try again.")


if __name__ == "__main__":
    main()
