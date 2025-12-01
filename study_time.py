import os
import time
from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd

data_file = "StudyTime.csv"
if os.path.exists(data_file):
    df = pd.read_csv(data_file)
    subjects = df["Subject"].unique().tolist()
else:
    subjects = []


def select_subject(subjects):
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
    # prints time when given in seconds
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
    print("Stopwatch started!")
    print("Commands:")
    print("  [c]  check elapsed time")
    print("  [s]  stop and save session")

    start_time = datetime.now()

    while True:
        cmd = input("Enter command (c/s): ").strip().lower()

        if cmd == "c":
            end_time = datetime.now()
            elapsed_seconds = end_time - start_time
            # transform to seconds and consider integer not float
            elapsed_seconds = (
                elapsed_seconds
                if type(elapsed_seconds) == int
                else int(elapsed_seconds.total_seconds())
            )
            print(f"You've studied for {format_time(elapsed_seconds)}\n")

        elif cmd == "s":
            end_time = datetime.now()
            elapsed_seconds = (
                elapsed_seconds
                if type(elapsed_seconds) == int
                else int(elapsed_seconds.total_seconds())
            )  # transform to seconds and consider integer not float
            print(
                f"You've studied for {format_time(elapsed_seconds)}\n"
            )
            return elapsed_seconds

        else:
            print("Invalid command. Use c/s.\n")


def log_study_time(subject, seconds):
    today = datetime.now().strftime("%Y-%m-%d")

    # Load existing CSV or create a new one
    if os.path.exists(data_file):
        df = pd.read_csv(data_file)
    else:
        df = pd.DataFrame(columns=["Date", "Subject", "Seconds"])

    # Create the new row for this session
    new_row = {"Date": today, "Subject": subject, "Seconds": seconds}

    # Append the row
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    # Save
    df.to_csv(data_file, index=False)

    print(f"Today you've studied {subject} for {format_time(seconds)}.\n")


def show_statistics():
    if not os.path.exists(data_file):
        print("No study data yet.")
        return

    df = pd.read_csv(data_file)

    print("\n====📊 Study Statistics 📊====")

    # Total minutes per subject
    print("\nTotal minutes per subject:")
    df_subj = df.groupby("Subject")["Seconds"].sum()
    print(df_subj.apply(format_time))

    # Daily totals
    print("\nTotal minutes per day:")
    df["Date"] = pd.to_datetime(df["Date"])
    df_date = df.groupby("Date")["Seconds"].sum()
    # Create complete date range from first study day to today
    full_range = pd.date_range(start=df["Date"].min(), end=pd.Timestamp.today())

    # Reindex → missing days become NaN → fill with 0
    df_date_full = df_date.reindex(full_range, fill_value=0)
    print(df_date_full.apply(format_time))

    # Overall total
    total_all = df["Seconds"].sum()
    print(f"\nOverall study time: {format_time(total_all)}\n")


def show_plots():
    df = pd.read_csv(data_file)
    df_subj = df.groupby("Subject")["Seconds"].sum()

    plt.figure(figsize=(6, 6))
    df_subj.plot(kind="pie", autopct="%1.1f%%")
    plt.title("Study Time Distribution by Subject")
    plt.ylabel("")
    plt.show()


def add_time():
    pass


# ---------- MAIN PROGRAM ----------


def main():
    while True:
        print("\n===== STUDY TRACKER =====")
        print("1. Start a study session")
        print("2. View statistics")
        print("3. View visual statistics")
        print("4. Exit")

        choice = input("Choose an option: ").strip()

        if choice == "1":
            subject = select_subject(subjects)
            minutes = start_stopwatch()
            log_study_time(subject, minutes)
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
